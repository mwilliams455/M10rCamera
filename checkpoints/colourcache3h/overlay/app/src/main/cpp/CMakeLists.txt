cmake_minimum_required(VERSION 3.6)

project(dngCreator)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_link_options("-Wl,-z,max-page-size=16384")

file(READ ${CMAKE_CURRENT_SOURCE_DIR}/../../../version.properties ver)
string(REGEX MATCH "VERSION_BUILD=([0-9]*)" _ ${ver})
set(VERSION_BUILD ${CMAKE_MATCH_1})
string(REGEX MATCH "VERSION_NAME=([0-9,.]*)" _ ${ver})
set(VERSION_NAME ${CMAKE_MATCH_1})

file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/deps/tiny_dng_writer.h" M10R_DEP_SHA)
if(NOT M10R_DEP_SHA STREQUAL "0c68ee68914b949eaf194a20d83505d4debee9272d991e68e538e25611f289cc")
    message(FATAL_ERROR "Pinned dependency changed: tiny_dng_writer.h")
endif()
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/deps/technicallyflac.h" M10R_DEP_SHA)
if(NOT M10R_DEP_SHA STREQUAL "7877dfd21152cd383812a860e18feab667ac8543c55a6b80118b9c1a5f654449")
    message(FATAL_ERROR "Pinned dependency changed: technicallyflac.h")
endif()
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/deps/archive.h" M10R_DEP_SHA)
if(NOT M10R_DEP_SHA STREQUAL "0e54cb7a280ed37535b430d8f8416817ad7ef18dc45e646a0ff53edc0ce2c3a5")
    message(FATAL_ERROR "Pinned dependency changed: archive.h")
endif()
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/deps/archive_entry.h" M10R_DEP_SHA)
if(NOT M10R_DEP_SHA STREQUAL "a8d2e0f18bf9b2ebd9eace883616e481cd5c6ea4f437b23640f90a3331b4506f")
    message(FATAL_ERROR "Pinned dependency changed: archive_entry.h")
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/deps)

set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR})

find_program(PYTHON3_EXECUTABLE python3)

# ---------------------------------------------------------------------------
# ncnn (prebuilt static lib under ncnn/<ABI>/)
#
# Both ML networks (FlowNet + KernelNet) are compiled into ONE shared library
# (libncnnMl.so) that
# links ncnn statically. The FlowNet model requires three custom layers
# (FlownetUpsample / FlownetCorrLookup / FlownetCorrFused) compiled from source
# and registered at runtime via Net::register_custom_layer().
#
# arm64-v8a: ncnn built with Vulkan → GPU inference, glslang .a linked.
# armeabi-v7a: ncnn built without Vulkan → CPU-only, no glslang needed.
# ---------------------------------------------------------------------------
set(NCNN_ABI_DIR "${CMAKE_CURRENT_SOURCE_DIR}/ncnn/${ANDROID_ABI}")
set(NCNN_INC_DIR "${NCNN_ABI_DIR}/include/ncnn")
set(NCNN_LIB_DIR "${NCNN_ABI_DIR}/lib")

if(EXISTS "${NCNN_LIB_DIR}/libncnn.a")
    # --- generate shader headers from .comp files (configure-time) ---
    set(SHADER_DIR "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/shader")
    set(GEN_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/flownet/gen_shader_header.py")
    set(GEN_OUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
    file(MAKE_DIRECTORY "${GEN_OUT_DIR}")

    set(VULKAN_LAYER_SRCS "")
    set(VULKAN_LIBS "")
    set(NCNN_VULKAN OFF)

    if(EXISTS "${NCNN_LIB_DIR}/libSPIRV.a")
        set(NCNN_VULKAN ON)
        # Vulkan layer sources — only compiled when glslang is present
        set(VULKAN_LAYER_SRCS
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetupsample_vulkan.cpp"
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetcorrlookup_vulkan.cpp"
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetcorrfused_vulkan.cpp"
        )
        set(VULKAN_LIBS
            "${NCNN_LIB_DIR}/libglslang.a"
            "${NCNN_LIB_DIR}/libMachineIndependent.a"
            "${NCNN_LIB_DIR}/libGenericCodeGen.a"
            "${NCNN_LIB_DIR}/libglslang-default-resource-limits.a"
            "${NCNN_LIB_DIR}/libOSDependent.a"
            "${NCNN_LIB_DIR}/libSPIRV.a"
        )
        # Generate shader headers (only needed for Vulkan path)
        foreach(shader flownetcorrfused flownetcorrlookup flownetupsample)
            set(out "${GEN_OUT_DIR}/${shader}_comp.h")
            execute_process(
                COMMAND "${PYTHON3_EXECUTABLE}" "${GEN_SCRIPT}"
                        "${SHADER_DIR}/${shader}.comp" "${shader}_comp_data"
                OUTPUT_FILE "${out}"
                RESULT_VARIABLE gen_result
            )
            if(NOT gen_result EQUAL 0)
                message(WARNING "Failed to generate ${shader}_comp.h")
            endif()
        endforeach()
    endif()

    add_library(ncnnMl SHARED
        ${SRC_DIR}/ncnnMl.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetupsample.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetcorrlookup.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetcorrfused.cpp
        ${VULKAN_LAYER_SRCS}
    )

    target_include_directories(ncnnMl PRIVATE
        "${NCNN_INC_DIR}"
        "${GEN_OUT_DIR}"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan"
    )

    # OpenMP: compile with -fopenmp so the default CPU impls of the custom
    # FlowNet layers (which use `#pragma omp parallel for num_threads(opt.num_threads)`)
    # actually parallelize. Statically link NDK's libomp.a so there is no
    # runtime libomp.so dependency and no runtime CPU/topology probing picks the
    # thread count — ncnnMl sets opt.num_threads explicitly.
    target_compile_options(ncnnMl PRIVATE
        -fno-rtti -fno-exceptions
        -fopenmp
    )

    execute_process(
        COMMAND "${CMAKE_CXX_COMPILER}" -print-resource-dir
        OUTPUT_VARIABLE NCNN_CLANG_RESOURCE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(ANDROID_ABI STREQUAL "arm64-v8a")
        set(NCNN_OMP_ARCH "aarch64")
    elseif(ANDROID_ABI STREQUAL "armeabi-v7a")
        set(NCNN_OMP_ARCH "arm")
    else()
        set(NCNN_OMP_ARCH "")
    endif()

    if(NCNN_OMP_ARCH AND EXISTS "${NCNN_CLANG_RESOURCE_DIR}/lib/linux/${NCNN_OMP_ARCH}/libomp.a")
        set(NCNN_OMP_LIB "${NCNN_CLANG_RESOURCE_DIR}/lib/linux/${NCNN_OMP_ARCH}/libomp.a")
    else()
        set(NCNN_OMP_LIB "")
        message(WARNING "OpenMP static library (libomp.a) not found for ${ANDROID_ABI}")
    endif()

    target_link_libraries(ncnnMl PRIVATE
        "${NCNN_LIB_DIR}/libncnn.a"
        ${VULKAN_LIBS}
        ${NCNN_OMP_LIB}
        android
        log
    )

    set_target_properties(ncnnMl PROPERTIES
        CXX_STANDARD 17
        CXX_STANDARD_REQUIRED ON
        CXX_EXTENSIONS OFF
    )

    message(STATUS "ncnn enabled for ${ANDROID_ABI} (Vulkan: ${NCNN_VULKAN})")
else()
    message(WARNING "ncnn prebuilt not found for ${ANDROID_ABI}; NcnnML disabled")
    # Generate stub JNI functions so the library loads without ncnn.
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/ncnnMl_stub.cpp"
        "#include <jni.h>\n"
        "extern \"C\" {\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_NcnnMl_nativeEnsureInit(JNIEnv*, jclass) { return JNI_TRUE; }\n"
        "JNIEXPORT jlong JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeCreate(JNIEnv*, jclass, jobject, jstring) { return 0; }\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeRun(JNIEnv*, jclass, jlong, jobject, jobject, jint, jint, jobject) { return JNI_FALSE; }\n"
        "JNIEXPORT void JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeDestroy(JNIEnv*, jclass, jlong) {}\n"
        "JNIEXPORT jlong JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeCreate(JNIEnv*, jclass, jobject, jstring) { return 0; }\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeRun(JNIEnv*, jclass, jlong, jobject, jint, jint, jfloat, jobject) { return JNI_FALSE; }\n"
        "JNIEXPORT void JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeDestroy(JNIEnv*, jclass, jlong) {}\n"
        "}\n"
    )
    add_library(ncnnMl SHARED
        "${CMAKE_CURRENT_BINARY_DIR}/ncnnMl_stub.cpp"
    )
    target_link_libraries(ncnnMl PRIVATE
        log
    )
endif()

add_library(${CMAKE_PROJECT_NAME} SHARED
    ${SRC_DIR}/dngCreator.cpp
    ${SRC_DIR}/m10rRender.cpp
)
set_source_files_properties(${SRC_DIR}/m10rRender.cpp PROPERTIES
    COMPILE_FLAGS "-O3 -ffp-contract=off"
)
add_library(allocator SHARED
    ${SRC_DIR}/allocator.cpp
    ${SRC_DIR}/rawF16.cpp
)
add_library(flacRecorder SHARED
    ${SRC_DIR}/flacRecorder.cpp
)

# --- MediaCinemaRAW (.mcraw) lossless raw-video encoder ---------------------
# Sources are globbed: dropping additional .cpp/.h files into
# src/main/cpp/mediacinemaraw/{,src} adds them to the build automatically.
# The test/ subdirectory is intentionally outside the glob.
file(GLOB MCRAW_SOURCES
        "${SRC_DIR}/mediacinemaraw/*.cpp"
        "${SRC_DIR}/mediacinemaraw/src/*.cpp"
)
add_library(mcraw SHARED ${MCRAW_SOURCES})
target_include_directories(mcraw PRIVATE "${SRC_DIR}/mediacinemaraw/include")
# Always optimize the encoder, including debug Gradle builds: unoptimized
# debug code multiplies the per-frame encode time several times over and
# starves the RAW video pipeline.
target_compile_options(mcraw PRIVATE -O3)
target_link_libraries(mcraw PRIVATE
        log
)
add_library(
        camera2native SHARED ${SRC_DIR}/native-engine.cpp
)

target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
        VERSION_BUILD="${VERSION_BUILD}"
        VERSION_NAME="${VERSION_NAME}"
)

target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE
        log
        dl
        jnigraphics
)

target_link_libraries(allocator PRIVATE
        log
        jnigraphics
)

target_link_libraries(flacRecorder PRIVATE
        log
)

target_link_libraries(
        camera2native
        log
)

# AMAZE1A isolated source-reconstruction library; existing native targets untouched.
add_library(m10ramaze SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/jni.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/amaze_m10r_fix1.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/border.cc
)
set_target_properties(m10ramaze PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
target_include_directories(m10ramaze PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/include)
# PREVIEW1B: AMaZE uses bounded std::thread workers. A static OpenMP runtime
# here aborts when another packaged native library has initialized its copy.
target_compile_options(m10ramaze PRIVATE -O2 -ffp-contract=off -fno-fast-math)
target_link_options(m10ramaze PRIVATE -Wl,--exclude-libs,ALL)

# --- Halide CPU burst alignment (arm64-v8a only) ----------------------------
# Prebuilt kernels from the halide-align project (stage 1: base pyramid once
# per burst; stage 2: per-frame tile matching) + the Halide arm64 runtime,
# wrapped for Java by align_jni.cpp. armeabi-v7a builds skip this library;
# HalideAlignment.java falls back to the GL pyramid path when it is absent.
if (${ANDROID_ABI} STREQUAL "arm64-v8a"
        AND EXISTS ${SRC_DIR}/halide/arm64-v8a/libhalide_runtime_android.a)
    add_library(halidealign SHARED ${SRC_DIR}/halide/align_jni.cpp)
    target_include_directories(halidealign PRIVATE
            ${SRC_DIR}/halide/include
            ${SRC_DIR}/halide/arm64-v8a)
    set_target_properties(halidealign PROPERTIES CXX_STANDARD 17)
    add_library(alignburst_base_f16 STATIC IMPORTED)
    set_target_properties(alignburst_base_f16 PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignburst_base_f16.a)
    add_library(alignburst_f16 STATIC IMPORTED)
    set_target_properties(alignburst_f16 PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignburst_f16.a)
    add_library(halide_runtime_android STATIC IMPORTED)
    set_target_properties(halide_runtime_android PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/libhalide_runtime_android.a)
    target_link_libraries(halidealign PRIVATE
            alignburst_base_f16
            alignburst_f16
            halide_runtime_android
            log
            dl)
endif()

# EXPOSURE1B measurement bridge; original target source/flags remain unchanged.
target_sources(${CMAKE_PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/m10rExposure1B.cpp)

# EXPOSURE1E: isolated metering-RAW preparation; no photographic/native target changes.
add_library(m10rexposureprep SHARED ${CMAKE_CURRENT_SOURCE_DIR}/m10rExposurePrep1E.cpp)
set_target_properties(m10rexposureprep PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
target_compile_options(m10rexposureprep PRIVATE -O3 -ffp-contract=off -fno-fast-math)
