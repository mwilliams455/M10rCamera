package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.media.Image;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** An owned, bounded copy of the Bayer patch used by spot WB. Sensor coordinates
 * remain full-frame coordinates for the existing crop, CFA and shading math. */
public final class M10RMeasuredFrame3N {
    public static final float FOV_RATIO = 0.05f;
    public static final int MAX_PATCH_BYTES = 2 * 1024 * 1024;

    public static final class View {
        public final float x, y;
        public final int width, height, gravityRotation;
        public View(float x, float y, int width, int height, int gravityRotation) {
            if (width <= 0 || height <= 0) throw new IllegalArgumentException("spot_view_geometry");
            this.x = x; this.y = y; this.width = width; this.height = height;
            this.gravityRotation = gravityRotation;
        }
    }

    public static final class Geometry {
        public final int sensorWidth, sensorHeight, centerX, centerY, boxSide;
        public final int startX, startY, endX, endY;
        private final Rect activeArray;
        private Geometry(int width, int height, int cx, int cy, int side,
                int x0, int y0, int x1, int y1, Rect active) {
            sensorWidth = width; sensorHeight = height; centerX = cx; centerY = cy;
            boxSide = side; startX = x0; startY = y0; endX = x1; endY = y1;
            activeArray = active == null ? null : new Rect(active);
        }
        public Rect copyActiveArray() { return activeArray == null ? null : new Rect(activeArray); }
    }

    public final Geometry geometry;
    public final int rowStride;
    private final byte[] bytes;
    private M10RMeasuredFrame3N(Geometry geometry, byte[] bytes) {
        this.geometry = geometry; this.bytes = bytes;
        rowStride = (geometry.endX - geometry.startX) * 2;
    }
    public ByteBuffer pixels() {
        return ByteBuffer.wrap(bytes).asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN);
    }

    /** Same view-to-sensor mapping as the spot sampler; no colour arithmetic. */
    public static Geometry geometry(int rawW, int rawH, CameraCharacteristics c,
            CaptureResult result, View view) {
        if (c == null || view == null || rawW < 16 || rawH < 16 || rawW > 32768 || rawH > 32768)
            throw new IllegalArgumentException("spot_sensor_geometry");
        Integer orientation = c.get(CameraCharacteristics.SENSOR_ORIENTATION);
        int sensorOrientation = orientation == null ? 90 : orientation;
        Integer facing = c.get(CameraCharacteristics.LENS_FACING);
        boolean mirrored = facing != null && facing == CameraCharacteristics.LENS_FACING_FRONT;
        int rotation = ((90 - sensorOrientation - view.gravityRotation) % 360 + 360) % 360;
        float u = view.x / view.width, v = view.y / view.height;
        if (mirrored) u = 1.0f - u;
        double rad = Math.toRadians(rotation), cos = Math.cos(rad), sin = Math.sin(rad);
        float dx = u - 0.5f, dy = v - 0.5f;
        float rx = (float) (dx * cos - dy * sin) + 0.5f;
        float ry = (float) (dx * sin + dy * cos) + 0.5f;
        Rect crop = result == null ? null : result.get(CaptureResult.SCALER_CROP_REGION);
        Rect active = c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        int left = 0, top = 0, width = rawW, height = rawH;
        if (crop != null && crop.width() > 0 && crop.height() > 0) {
            left = Math.max(0, crop.left); top = Math.max(0, crop.top);
            width = Math.min(rawW - left, crop.width()); height = Math.min(rawH - top, crop.height());
        } else if (active != null && active.width() > 0 && active.height() > 0) {
            left = Math.max(0, active.left); top = Math.max(0, active.top);
            width = Math.min(rawW - left, active.width()); height = Math.min(rawH - top, active.height());
        }
        if (width < 16 || height < 16) throw new IllegalArgumentException("spot_crop_geometry");
        int cx = Math.max(0, Math.min(rawW - 1, left + Math.round(rx * width)));
        int cy = Math.max(0, Math.min(rawH - 1, top + Math.round(ry * height)));
        int side = Math.max(16, Math.round(Math.min(width, height) * FOV_RATIO)) & ~1;
        int x0 = Math.max(left, Math.min(left + width - side, cx - side / 2)) & ~1;
        int y0 = Math.max(top, Math.min(top + height - side, cy - side / 2)) & ~1;
        int x1 = Math.min(left + width, x0 + side), y1 = Math.min(top + height, y0 + side);
        if (x0 < 0 || y0 < 0 || x1 > rawW || y1 > rawH || x1 <= x0 || y1 <= y0
                || ((x1 - x0) & 1) != 0 || ((y1 - y0) & 1) != 0)
            throw new IllegalArgumentException("spot_bayer_patch_geometry");
        return new Geometry(rawW, rawH, cx, cy, side, x0, y0, x1, y1, active);
    }

    /** Called while transport retirement is excluded. Copies only the sampled ROI,
     * unpacks RAW10/12 to unchanged integer sensels, and always releases the Image. */
    public static M10RMeasuredFrame3N copyAndClose(Image image, long timestamp,
            CameraCharacteristics c, CaptureResult result, View view) {
        try {
            if (image == null || image.getTimestamp() != timestamp)
                throw new IllegalArgumentException("spot_raw_timestamp");
            int format = image.getFormat(), width = image.getWidth(), height = image.getHeight();
            if (format != ImageFormat.RAW_SENSOR && format != ImageFormat.RAW10 && format != ImageFormat.RAW12)
                throw new IllegalArgumentException("spot_raw_format");
            Rect crop = image.getCropRect();
            if (crop == null || crop.left != 0 || crop.top != 0 || crop.right != width || crop.bottom != height)
                throw new IllegalArgumentException("spot_raw_image_crop");
            Geometry g = geometry(width, height, c, result, view);
            long count = (long) (g.endX - g.startX) * (g.endY - g.startY);
            if (count <= 0 || count * 2 > MAX_PATCH_BYTES)
                throw new IllegalArgumentException("spot_patch_allocation_limit");
            Image.Plane[] planes = image.getPlanes();
            if (planes == null || planes.length != 1) throw new IllegalArgumentException("spot_raw_planes");
            Image.Plane plane = planes[0];
            int row = plane.getRowStride(), pixel = plane.getPixelStride();
            if (pixel <= 0) pixel = 2;
            long requiredRow = format == ImageFormat.RAW10 ? ((long) width + 3) / 4 * 5
                    : format == ImageFormat.RAW12 ? ((long) width + 1) / 2 * 3 : (long) (width - 1) * pixel + 2;
            if (row < requiredRow || pixel < 2) throw new IllegalArgumentException("spot_raw_stride");
            ByteBuffer source = plane.getBuffer().duplicate().order(ByteOrder.LITTLE_ENDIAN);
            int origin = source.position();
            if ((long) origin + (long) (height - 1) * row + requiredRow > source.limit())
                throw new IllegalArgumentException("spot_short_raw_buffer");
            byte[] data = new byte[(int) count * 2];
            int target = 0;
            for (int y = g.startY; y < g.endY; y++) {
                for (int x = g.startX; x < g.endX; x++) {
                    int value, offset;
                    if (format == ImageFormat.RAW10) {
                        offset = origin + y * row + (x / 4) * 5;
                        value = ((source.get(offset + x % 4) & 255) << 2)
                                | ((source.get(offset + 4) >> ((x % 4) * 2)) & 3);
                    } else if (format == ImageFormat.RAW12) {
                        offset = origin + y * row + (x / 2) * 3;
                        value = ((source.get(offset + x % 2) & 255) << 4)
                                | ((source.get(offset + 2) >> ((x % 2) * 4)) & 15);
                    } else value = source.getShort(origin + y * row + x * pixel) & 65535;
                    data[target++] = (byte) value; data[target++] = (byte) (value >>> 8);
                }
            }
            return new M10RMeasuredFrame3N(g, data);
        } finally {
            if (image != null) image.close();
        }
    }
}
