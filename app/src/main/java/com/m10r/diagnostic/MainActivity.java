package com.m10r.diagnostic;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.FileInputStream;
import java.nio.channels.FileChannel;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int REQUEST_DNG = 1001;

    private EditText neutralR;
    private EditText neutralG;
    private EditText neutralB;
    private TextView result;
    private TextView fileStatus;
    private ImageView previewView;
    private Bitmap previewBitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic v0.4");
        title.setTextSize(22f);
        root.addView(title);

        TextView status = new TextView(this);
        status.setText(M10RColorSpecCore.selfCheckReport());
        status.setTextSize(15f);
        status.setPadding(0, pad / 2, 0, pad);
        root.addView(status);

        TextView instruction = new TextView(this);
        instruction.setText("AsShotNeutral (R / G / B)");
        root.addView(instruction);

        neutralR = addNumberField(root, "0.2853957637");
        neutralG = addNumberField(root, "1.0");
        neutralB = addNumberField(root, "0.6564102564");

        Button recover = new Button(this);
        recover.setText("Recover CA9 gains");
        recover.setOnClickListener(v -> recoverGains());
        root.addView(recover);

        result = new TextView(this);
        result.setText("Expected fixture #1: [897, 256, 390]");
        result.setPadding(0, pad / 2, 0, pad);
        root.addView(result);

        Button choose = new Button(this);
        choose.setText("Choose M10-R DNG + Build Sensor Preview");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        previewView = new ImageView(this);
        previewView.setAdjustViewBounds(true);
        previewView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        previewView.setContentDescription("v0.4 M10-R sensor sanity preview");
        root.addView(previewView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. v0.4 preserves the pixel-exact compression-7 SOF3 decoder, then resolves the actual DNG Bayer pattern, normalizes against DNG black/white levels, bilinear demosaics a bounded sensor preview, applies diagnostic AsShotNeutral WB, and encodes to sRGB. Full Leica rendering remains disabled.");
        fileStatus.setPadding(0, pad / 2, 0, 0);
        fileStatus.setTextIsSelectable(true);
        root.addView(fileStatus);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
    }

    private EditText addNumberField(LinearLayout root, String value) {
        EditText field = new EditText(this);
        field.setInputType(android.text.InputType.TYPE_CLASS_NUMBER |
                android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL |
                android.text.InputType.TYPE_NUMBER_FLAG_SIGNED);
        field.setText(value);
        field.setSelectAllOnFocus(true);
        root.addView(field);
        return field;
    }

    private void recoverGains() {
        try {
            double[] neutral = {
                    Double.parseDouble(neutralR.getText().toString().trim()),
                    Double.parseDouble(neutralG.getText().toString().trim()),
                    Double.parseDouble(neutralB.getText().toString().trim())
            };
            showRecoveredGains(neutral);
        } catch (RuntimeException ex) {
            result.setText("Input error: " + ex.getMessage());
        }
    }

    private void showRecoveredGains(double[] neutral) {
        int[] gains = M10RColorSpecCore.recoverCa9Gains(neutral);
        double[] rebuilt = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
        result.setText(String.format(Locale.US,
                "CA9 gains = [%d, %d, %d]\nFirmware neutral = [%.10f, %.10f, %.10f]",
                gains[0], gains[1], gains[2], rebuilt[0], rebuilt[1], rebuilt[2]));
    }

    private void chooseDng() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {
                "image/x-adobe-dng", "image/dng", "image/x-dng", "application/octet-stream"
        });
        startActivityForResult(intent, REQUEST_DNG);
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_DNG || resultCode != RESULT_OK || data == null) return;
        Uri uri = data.getData();
        if (uri == null) return;
        try {
            getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (SecurityException ignored) {
            // A transient grant is sufficient for this immediate diagnostic read.
        }
        clearPreview();
        fileStatus.setText("Reading DNG metadata, decoding lossless-JPEG CFA, and building v0.4 sensor preview…\n" + uri);
        new Thread(() -> parseDecodeAndPreviewDng(uri), "m10r-dng-preview").start();
    }

    private void parseDecodeAndPreviewDng(Uri uri) {
        try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
            if (pfd == null) throw new IllegalStateException("content provider returned no file descriptor");
            try (FileInputStream in = new FileInputStream(pfd.getFileDescriptor());
                 FileChannel channel = in.getChannel()) {
                DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
                final String rawDiagnostic;
                final SensorPreviewCore.PreviewResult preview;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    preview = SensorPreviewCore.render(raw, info);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nLEGACY NOTE: the v0.3 decoder summary names parity planes as RGGB. " +
                            "Those labels are diagnostic-only; v0.4 resolves the actual DNG CFA below and does not alter decoded samples." +
                            "\n\nDECODER STATUS: PIXEL-EXACT CFA PRESERVED; SENSOR PREVIEW BUILT.";
                } else if (info.compression == 1) {
                    preview = null;
                    rawDiagnostic = "RAW decode not run: this file is uncompressed CFA; v0.4 preserves the proven M10-R compression-7 path.";
                } else {
                    preview = null;
                    rawDiagnostic = "RAW decode not run: unsupported compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic, preview));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> {
                clearPreview();
                fileStatus.setText("DNG v0.4 preview failed: " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
            });
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info,
                              String rawDiagnostic, SensorPreviewCore.PreviewResult preview) {
        if (info.asShotNeutral != null && info.asShotNeutral.length == 3) {
            neutralR.setText(String.format(Locale.US, "%.10f", info.asShotNeutral[0]));
            neutralG.setText(String.format(Locale.US, "%.10f", info.asShotNeutral[1]));
            neutralB.setText(String.format(Locale.US, "%.10f", info.asShotNeutral[2]));
            try {
                showRecoveredGains(info.asShotNeutral);
            } catch (RuntimeException ex) {
                result.setText("AsShotNeutral found, but CA9 recovery failed: " + ex.getMessage());
            }
        } else {
            result.setText("AsShotNeutral was not found as a three-channel DNG field.");
        }

        String previewDiagnostic;
        if (preview != null) {
            Bitmap next = Bitmap.createBitmap(preview.argb, preview.width, preview.height, Bitmap.Config.ARGB_8888);
            Bitmap old = previewBitmap;
            previewBitmap = next;
            previewView.setImageBitmap(next);
            if (old != null && old != next && !old.isRecycled()) old.recycle();
            previewDiagnostic = preview.diagnosticSummary();
        } else {
            clearPreview();
            previewDiagnostic = "v0.4 sensor preview not available for this DNG.";
        }

        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\n" + previewDiagnostic +
                "\n\nBoundary: v0.4 proves CFA interpretation, normalization, demosaic geometry, and diagnostic WB only. Full Leica CA9/CC0/MEDIUM-tone/DG/CC1 rendering remains intentionally disabled.");
    }

    private void clearPreview() {
        if (previewView != null) previewView.setImageDrawable(null);
        Bitmap old = previewBitmap;
        previewBitmap = null;
        if (old != null && !old.isRecycled()) old.recycle();
    }

    @Override
    protected void onDestroy() {
        clearPreview();
        super.onDestroy();
    }
}
