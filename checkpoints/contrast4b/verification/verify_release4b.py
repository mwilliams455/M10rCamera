#!/usr/bin/env python3
"""Read-only APK/build verification for CONTRAST4B; writes one JSON evidence report.

This helper never runs Gradle, signs an APK, edits app inputs, or reads the
private signing keystore. Invoke only after the root build/test run completes.
"""
from __future__ import annotations
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

VERIFY = Path(__file__).resolve().parent
WORK = VERIFY.parent
PROJECT = WORK / "PhotonCamera"
DEPS = WORK / "deps"
BUILD_TOOLS = DEPS / "sdk/build-tools/35.0.0"
BASELINE = WORK / "inputs/M10RCam_RAWSTREAMS4A_TEST.apk"
BASELINE_SHA = "d7fa707f109b62ea742ebcd4d14f5104b6a6aeb10ab5e169e39586d7c61ef293"
PACKAGE = "com.m10rproject.m10rcam.photon"
VERSION_CODE = "29007"
VERSION_NAME = "1.48-m10r-contrast4b-test"

def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def file_record(path):
    stat = path.stat()
    return {"path": str(path), "bytes": stat.st_size, "sha256": sha_file(path),
            "mtimeNs": stat.st_mtime_ns}

def invoke(command):
    env = os.environ.copy()
    env["JAVA_HOME"] = str(DEPS / "jdk17")
    env["PATH"] = str(DEPS / "jdk17/bin") + os.pathsep + env.get("PATH", "")
    result = subprocess.run([str(x) for x in command], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if result.returncode:
        raise RuntimeError("Read-only command failed (exit %d): %s\n%s" %
                           (result.returncode, " ".join(str(x) for x in command),
                            (result.stdout + "\n" + result.stderr)[-5000:]))
    return result.stdout, result.stderr

def apk_identity(apk):
    output, _ = invoke([BUILD_TOOLS / "aapt", "dump", "badging", apk])
    line = next((line for line in output.splitlines() if line.startswith("package:")), None)
    if line is None:
        raise ValueError("aapt did not return package identity for " + str(apk))
    values = dict(re.findall(r"(\w+)='([^']*)'", line))
    return {"package": values.get("name"), "versionCode": values.get("versionCode"),
            "versionName": values.get("versionName"),
            "minSdk": next((re.search(r"'([^']+)'", line).group(1)
                            for line in output.splitlines() if line.startswith("sdkVersion:")), None),
            "targetSdk": next((re.search(r"'([^']+)'", line).group(1)
                               for line in output.splitlines() if line.startswith("targetSdkVersion:")), None)}

def apk_signature(apk):
    output, error = invoke([BUILD_TOOLS / "apksigner", "verify", "--verbose", "--print-certs", apk])
    certificates = []
    for line in output.splitlines():
        match = re.fullmatch(r"Signer #(\d+) certificate SHA-256 digest:\s*([0-9a-fA-F:]+)", line.strip())
        if match:
            certificates.append({"signer": int(match.group(1)),
                                 "certificateSha256": match.group(2).replace(":", "").lower()})
    if not certificates:
        raise ValueError("No signer SHA-256 digest returned by apksigner")
    schemes = {}
    for line in output.splitlines():
        match = re.fullmatch(r"Verified using (.+?):\s*(true|false)", line.strip())
        if match:
            schemes[match.group(1)] = match.group(2) == "true"
    if not schemes or not any(schemes.values()):
        raise ValueError("No successful APK signature scheme returned")
    return {"verified": True, "certificates": sorted(certificates, key=lambda x: x["signer"]),
            "signatureSchemes": schemes, "verificationExitCode": 0,
            "warnings": [line for line in (output + "\n" + error).splitlines()
                         if line.strip().startswith("WARNING:")]}

def apk_payloads(apk):
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("APK has duplicate ZIP entry names")
        records = {}
        for name in names:
            if not ((name.startswith("lib/") and name.endswith(".so")) or
                    (name.startswith("assets/") and not name.endswith("/"))):
                continue
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            records[name] = {"bytes": archive.getinfo(name).file_size, "sha256": digest.hexdigest()}
        return {
            "nativeLibraries": {name: value for name, value in records.items() if name.startswith("lib/")},
            "assets": {name: value for name, value in records.items() if name.startswith("assets/")},
        }

def compare_payloads(old, new):
    missing = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    modified = [{"path": name, "baseline": old[name], "current": new[name]}
                for name in sorted(set(old) & set(new)) if old[name] != new[name]]
    return {"baselineCount": len(old), "currentCount": len(new),
            "unchangedInheritedCount": sum(name in new and old[name] == new[name] for name in old),
            "missing": missing, "added": added, "modified": modified,
            "allInheritedIdentical": not missing and not modified,
            "sameEntrySet": not missing and not added,
            "baseline": old, "current": new}

def compiled_build_config():
    relative = Path("com/particlesdevs/photoncamera/BuildConfig.class")
    class_root = PROJECT / "app/build/intermediates/javac/debug/compileDebugJavaWithJavac/classes"
    compiled = class_root / relative
    output, _ = invoke([DEPS / "jdk17/bin/javap", "-constants", "-classpath", class_root,
                        "com.particlesdevs.photoncamera.BuildConfig"])
    required = {
        "M10R_DETAIL3D": r"public static final boolean M10R_DETAIL3D = (true|false);",
        "VERSION_CODE": r"public static final int VERSION_CODE = (\d+);",
        "VERSION_NAME": r'public static final java\.lang\.String VERSION_NAME = "([^"]*)";',
        "APPLICATION_ID": r'public static final java\.lang\.String APPLICATION_ID = "([^"]*)";',
    }
    values = {}
    for name, pattern in required.items():
        match = re.search(pattern, output)
        if match is None:
            raise ValueError("Compiled BuildConfig constant missing: " + name)
        values[name] = match.group(1)
    values["M10R_DETAIL3D"] = values["M10R_DETAIL3D"] == "true"
    generated = PROJECT / "app/build/generated/source/buildConfig/debug/com/particlesdevs/photoncamera/BuildConfig.java"
    return {"class": file_record(compiled), "constants": values,
            "generatedSource": file_record(generated),
            "evidenceScope": "Compiled build output supporting the selected build flag, alongside the signed APK identity and stable build-input record."}

def selected_patterns(arguments):
    patterns = []
    iterator = iter(arguments)
    for item in iterator:
        if item == "--tests":
            patterns.append(next(iterator))
        elif item.startswith("--tests="):
            patterns.append(item.split("=", 1)[1])
    return patterns

def junit_evidence(run_path, run):
    patterns = selected_patterns(run.get("tasks", []))
    if not patterns:
        raise ValueError("Final run record has no explicit --tests selectors")
    test_source = PROJECT / "app/src/test/java"
    source_classes = {}
    for source in test_source.rglob("*.java"):
        text = source.read_text()
        package = re.search(r"^\s*package\s+([\w.]+)\s*;", text, re.M)
        if package:
            name = package.group(1) + "." + source.stem
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
                source_classes[name] = source
    if not source_classes:
        raise ValueError("No current test classes match the final run selectors")
    unmatched_patterns = [pattern for pattern in patterns
                          if not any(fnmatch.fnmatchcase(name, pattern) for name in source_classes)]
    xml_root = PROJECT / "app/build/test-results/testDebugUnitTest"
    if not xml_root.is_dir():
        raise ValueError("JUnit XML directory is absent: " + str(xml_root))
    log_path = run_path.with_suffix("").with_suffix(".log")
    if run_path.name.endswith(".run.json"):
        log_path = run_path.with_name(run_path.name[:-9] + ".log")
    log = log_path.read_text() if log_path.exists() else ""
    outcomes = re.findall(r"^> Task :app:testDebugUnitTest(?: ([A-Z][A-Z-]*))?\s*$", log, re.M)
    outcome = outcomes[-1] if outcomes else None
    cache_reused = outcome in ("UP-TO-DATE", "FROM-CACHE")
    log_start_ns = log_path.stat().st_mtime_ns
    # The runner opens a new log before starting Gradle. Birth time is not
    # portable; the run's log contains the test-task outcome and XML timestamps
    # are recorded below without pretending log mtime is its creation time.
    suites = []
    seen = set()
    xml_paths = sorted(xml_root.glob("TEST-*.xml"))
    for path in xml_paths:
        root = ET.parse(path).getroot()
        nodes = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        for suite in nodes:
            name = suite.get("name", "")
            if name not in source_classes:
                continue
            if name in seen:
                raise ValueError("Duplicate selected JUnit suite: " + name)
            seen.add(name)
            failures = []
            for test in suite.findall("testcase"):
                for tag in ("failure", "error"):
                    for item in test.findall(tag):
                        failures.append({"test": test.get("name"), "kind": tag,
                                         "type": item.get("type"), "message": item.get("message"),
                                         "detail": (item.text or "")[-3000:]})
            counts = {key: int(suite.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")}
            suites.append({
                "class": name, **counts, "seconds": float(suite.get("time", "0")),
                "timestamp": suite.get("timestamp"), "xml": file_record(path),
                "testSource": file_record(source_classes[name]), "failureDetails": failures,
            })
    missing = sorted(set(source_classes) - seen)
    totals = {key: sum(suite[key] for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    totals["executedWithoutFailureOrError"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    contrast_suites = [suite for suite in suites if ".M10RContrast" in suite["class"]]
    return {
        "selectors": patterns, "expectedClasses": sorted(source_classes),
        "unmatchedSelectors": unmatched_patterns, "missingClasses": missing,
        "suiteCount": len(suites), "totals": totals, "suites": suites,
        "allMatchedSuitesPresent": not missing,
        "allRequestedSelectorsResolved": not unmatched_patterns,
        "allMatchedSuitesPassing": (not missing and totals["tests"] > 0
                                   and totals["failures"] == 0 and totals["errors"] == 0),
        "allContrastTestsExecuted": bool(contrast_suites) and all(
            suite["tests"] > 0 and suite["skipped"] == 0 for suite in contrast_suites),
        "gradleTestTaskOutcome": outcome or ("EXECUTED" if outcomes else "not_found_in_log"),
        "gradleReusedTestOutputs": cache_reused,
        "finalRunLog": str(log_path), "logLastModifiedNs": log_start_ns,
        "freshnessBoundary": "Selection comes from the completed final run. The final run must succeed with stable app inputs; XML source hashes are cross-checked against that run below.",
    }

def app_inputs_evidence(run):
    before = run.get("applicationInputsBefore")
    after = run.get("applicationInputsAfter")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("Final run record lacks the application input hash snapshots")
    missing, modified = [], []
    for relative, expected in after.items():
        path = PROJECT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha_file(path) != expected:
            modified.append(relative)
    current = {str(path.relative_to(PROJECT))
               for directory in (PROJECT / "app/src", PROJECT / "circularbarlib/src")
               for path in directory.rglob("*") if path.is_file()}
    current.update(str(PROJECT / name).removeprefix(str(PROJECT) + "/")
                   for name in ("app/build.gradle", "circularbarlib/build.gradle",
                                "build.gradle", "settings.gradle", "gradle.properties"))
    added = sorted(current - set(after))
    return {"recordedInputCount": len(after),
            "beforeEqualsAfter": before == after,
            "runnerReportedStable": run.get("applicationInputsStableDuringBuild") is True,
            "missingCurrentInputs": sorted(missing), "modifiedCurrentInputs": sorted(modified),
            "addedCurrentInputs": added,
            "currentInputsMatchCompletedBuild": not missing and not modified and not added}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, required=True,
                        help="The successful final BUILD_CONTRAST4B*.run.json")
    parser.add_argument("--apk", type=Path,
                        help="Signed new APK; defaults to the sole debug output APK")
    parser.add_argument("--baseline-apk", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path, default=VERIFY / "RELEASE_CONTRAST4B.json")
    args = parser.parse_args()
    result = {
        "format": "m10r-contrast4b-release-verification-v1",
        "verifiedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "expected": {"package": PACKAGE, "versionCode": VERSION_CODE, "versionName": VERSION_NAME,
                     "baselineApkSha256": BASELINE_SHA, "inheritedNativeLibraries": 31, "inheritedAssets": 279},
        "readOnlyVerification": True, "privateSigningKeystoreRead": False,
        "gradleInvoked": False, "failures": [], "coverageWarnings": [],
    }
    def section(name, action):
        try:
            value = action()
            result[name] = value
            return value
        except Exception as error:
            result["failures"].append({"check": name, "reason": str(error)})
            return None
    def require(ok, check, reason):
        if not ok:
            result["failures"].append({"check": check, "reason": reason})

    apk = args.apk
    if apk is None:
        outputs = sorted((PROJECT / "app/build/outputs/apk/debug").glob("*.apk"))
        if len(outputs) != 1:
            result["failures"].append({"check": "apk_path",
                                      "reason": "Expected exactly one debug APK; pass --apk explicitly. Found: " +
                                                ", ".join(str(path) for path in outputs)})
        else:
            apk = outputs[0]
    run = section("completedBuildRun", lambda: json.loads(args.run_json.read_text()))
    if run is not None:
        result["completedBuildRun"] = {
            "record": file_record(args.run_json), "exitCode": run.get("exitCode"),
            "tasks": run.get("tasks"), "online": run.get("online"),
            "applicationInputsStableDuringBuild": run.get("applicationInputsStableDuringBuild"),
        }
        require(run.get("exitCode") == 0, "build_exit", "Completed root Gradle run did not succeed")
        inputs = section("buildInputs", lambda: app_inputs_evidence(run))
        if inputs:
            require(inputs["beforeEqualsAfter"] and inputs["runnerReportedStable"] and
                    inputs["currentInputsMatchCompletedBuild"], "build_inputs",
                    "App inputs changed during or after the completed build")
        junit = section("junit", lambda: junit_evidence(args.run_json, run))
        if junit:
            require(junit["allMatchedSuitesPassing"], "junit",
                    "Matched JUnit suites are missing, empty, failing, or contain errors")
            if junit["unmatchedSelectors"]:
                result["coverageWarnings"].append({
                    "check": "unmatched_test_selectors",
                    "selectors": junit["unmatchedSelectors"],
                    "reason": "Requested filters match no source test class; they were not executed and are not counted as passing tests.",
                })
            require(junit["allContrastTestsExecuted"], "contrast_junit",
                    "New contrast suites are missing, empty, or skipped")

    baseline_info = section("baselineApk", lambda: file_record(args.baseline_apk))
    if baseline_info:
        require(baseline_info["sha256"] == BASELINE_SHA, "baseline_identity",
                "Named baseline APK differs from the independently verified RAWSTREAMS4A APK")
    old_identity = section("baselineIdentity", lambda: apk_identity(args.baseline_apk))
    old_signature = section("baselineSignature", lambda: apk_signature(args.baseline_apk))
    old_payload = section("_baselinePayloads", lambda: apk_payloads(args.baseline_apk))
    if old_identity:
        require(old_identity["package"] == PACKAGE and old_identity["versionCode"] == "29006" and
                old_identity["versionName"] == "1.47-m10r-rawstreams4a-test",
                "baseline_package_version", "Unexpected RAWSTREAMS4A package or version")

    if apk is not None:
        current_info = section("apk", lambda: file_record(apk))
        identity = section("apkIdentity", lambda: apk_identity(apk))
        signature = section("apkSignature", lambda: apk_signature(apk))
        payload = section("_currentPayloads", lambda: apk_payloads(apk))
        if identity:
            require(identity["package"] == PACKAGE and identity["versionCode"] == VERSION_CODE and
                    identity["versionName"] == VERSION_NAME,
                    "apk_package_version", "Signed APK does not have the expected 4B package/version")
        if signature and old_signature:
            equal = signature["certificates"] == old_signature["certificates"]
            result["signingCertificateMatches4A"] = equal
            require(equal, "signing_certificate", "APK signer certificate digest differs from 4A")
        if payload and old_payload:
            libs = compare_payloads(old_payload["nativeLibraries"], payload["nativeLibraries"])
            assets = compare_payloads(old_payload["assets"], payload["assets"])
            result["nativeLibraries"] = libs
            result["assets"] = assets
            require(libs["baselineCount"] == 31 and libs["allInheritedIdentical"] and libs["sameEntrySet"],
                    "native_libraries", "The 31 inherited native libraries are not all present and byte-identical")
            require(assets["baselineCount"] == 279 and assets["allInheritedIdentical"],
                    "inherited_assets", "The 279 inherited assets are not all present and byte-identical")
        if current_info:
            stable = sha_file(apk) == current_info["sha256"]
            result["apkStableDuringVerification"] = stable
            require(stable, "apk_stability", "APK changed while verification was running")

    compiled = section("compiledBuildConfig", compiled_build_config)
    if compiled:
        constants = compiled["constants"]
        require(constants["M10R_DETAIL3D"], "compiled_detail_flag", "Compiled DETAIL3D flag is false")
        require(constants["APPLICATION_ID"] == PACKAGE and constants["VERSION_CODE"] == VERSION_CODE and
                constants["VERSION_NAME"] == VERSION_NAME,
                "compiled_version", "Compiled BuildConfig does not match the intended signed APK identity")

    result.pop("_baselinePayloads", None)
    result.pop("_currentPayloads", None)
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, args.output)
    summary = {
        "status": result["status"], "report": str(args.output), "failures": result["failures"],
        "coverageWarnings": result["coverageWarnings"],
        "apk": result.get("apk"), "identity": result.get("apkIdentity"),
        "signingCertificateMatches4A": result.get("signingCertificateMatches4A"),
        "signatureSchemes": result.get("apkSignature", {}).get("signatureSchemes"),
        "nativeLibrariesIdentical": result.get("nativeLibraries", {}).get("unchangedInheritedCount"),
        "inheritedAssetsIdentical": result.get("assets", {}).get("unchangedInheritedCount"),
        "compiledDetail3D": result.get("compiledBuildConfig", {}).get("constants", {}).get("M10R_DETAIL3D"),
        "junitSuites": result.get("junit", {}).get("suiteCount"),
        "junitTotals": result.get("junit", {}).get("totals"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
