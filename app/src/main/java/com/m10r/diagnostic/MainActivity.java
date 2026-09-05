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
    private ImageView sensorPreviewView;
    private ImageView leicaPreviewView;
    private Bitmap sensorPreviewBitmap;
    private Bitmap leicaPreviewBitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic v0.5");
        title.setTextSize(22f);
        root.addView(title);

        TextView status = new TextView(this);
        status.setText(M10RColorSpecCore.selfCheckReport() +
                "\n\nv0.5: Leica locus / NeutralToXY / interpolated CM / CC0 / default sRGB CC1 are wired as a linear reference. MEDIUM tone and Differential Gamma remain disabled.");
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
        choose.setText("Choose M10-R DNG + Build v0.5 References");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        TextView sensorLabel = new TextView(this);
        sensorLabel.setText("v0.4 SENSOR SANITY (frozen)");
        sensorLabel.setTextSize(16f);
        sensorLabel.setPadding(0, pad / 2, 0, pad / 4);
        root.addView(sensorLabel);

        sensorPreviewView = new ImageView(this);
        sensorPreviewView.setAdjustViewBounds(true);
        sensorPreviewView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        sensorPreviewView.setContentDescription("v0.4 M10-R sensor sanity preview");
        root.addView(sensorPreviewView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView leicaLabel = new TextView(this);
        leicaLabel.setText("v0.5 LEICA LINEAR REFERENCE (no MEDIUM tone / DG yet)");
        leicaLabel.setTextSize(16f);
        leicaLabel.setPadding(0, pad / 2, 0, pad / 4);
        root.addView(leicaLabel);

        leicaPreviewView = new ImageView(this);
        leicaPreviewView.setAdjustViewBounds(true);
        leicaPreviewView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        leicaPreviewView.setContentDescription("v0.5 M10-R Leica linear reference preview");
        root.addView(leicaPreviewView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. v0.5 preserves the proven pixel-exact decoder and v0.4 sensor preview, then adds the recovered Leica linear ColorSpec path. The validated M10-R illuminant pair 17/21 uses an explicitly-labelled first-parity nominal A/D65 temperature bridge; nonlinear MEDIUM tone and Differential Gamma remain disabled.");
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
        clearPreviews();
        fileStatus.setText("Reading DNG, preserving v0.4 sensor path, and building v0.5 Leica linear reference…\n" + uri);
        new Thread(() -> parseDecodeAndRenderDng(uri), "m10r-dng-v050").start();
    }

    private void parseDecodeAndRenderDng(Uri uri) {
        try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
            if (pfd == null) throw new IllegalStateException("content provider returned no file descriptor");
            try (FileInputStream in = new FileInputStream(pfd.getFileDescriptor());
                 FileChannel channel = in.getChannel()) {
                DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
                final String rawDiagnostic;
                final SensorPreviewCore.PreviewResult sensorPreview;
                final M10RLinearReferenceRenderer.Result leicaPreview;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    sensorPreview = SensorPreviewCore.render(raw, info);
                    leicaPreview = M10RLinearReferenceRenderer.render(raw, info);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nLEGACY NOTE: the decoder summary's RGGB parity names are diagnostic-only; actual CFA is resolved separately." +
                            "\n\nDECODER STATUS: PIXEL-EXACT CFA PRESERVED; v0.4 SENSOR + v0.5 LEICA LINEAR REFERENCES BUILT.";
                } else {
                    sensorPreview = null;
                    leicaPreview = null;
                    rawDiagnostic = "Reference render not run: v0.5 intentionally preserves the proven M10-R compression-7 path; compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic, sensorPreview, leicaPreview));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> {
                clearPreviews();
                fileStatus.setText("DNG v0.5 reference render failed: " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
            });
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info,
                              String rawDiagnostic,
                              SensorPreviewCore.PreviewResult sensorPreview,
                              M10RLinearReferenceRenderer.Result leicaPreview) {
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

        String sensorDiagnostic;
        if (sensorPreview != null) {
            Bitmap next = Bitmap.createBitmap(sensorPreview.argb, sensorPreview.width,
                    sensorPreview.height, Bitmap.Config.ARGB_8888);
            Bitmap old = sensorPreviewBitmap;
            sensorPreviewBitmap = next;
            sensorPreviewView.setImageBitmap(next);
            if (old != null && old != next && !old.isRecycled()) old.recycle();
            sensorDiagnostic = sensorPreview.diagnosticSummary();
        } else {
            sensorDiagnostic = "v0.4 sensor preview unavailable.";
        }

        String leicaDiagnostic;
        if (leicaPreview != null) {
            Bitmap next = Bitmap.createBitmap(leicaPreview.argb, leicaPreview.width,
                    leicaPreview.height, Bitmap.Config.ARGB_8888);
            Bitmap old = leicaPreviewBitmap;
            leicaPreviewBitmap = next;
            leicaPreviewView.setImageBitmap(next);
            if (old != null && old != next && !old.isRecycled()) old.recycle();
            leicaDiagnostic = leicaPreview.diagnosticSummary();
        } else {
            leicaDiagnostic = "v0.5 Leica linear reference unavailable.";
        }

        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\n" + sensorDiagnostic + "\n\n" + leicaDiagnostic +
                "\n\nBoundary: v0.5 adds the recovered linear Leica color stage while keeping v0.4 frozen. MEDIUM tone and Differential Gamma remain the next nonlinear seam.");
    }

    private void clearPreviews() {
        if (sensorPreviewView != null) sensorPreviewView.setImageDrawable(null);
        if (leicaPreviewView != null) leicaPreviewView.setImageDrawable(null);
        Bitmap oldSensor = sensorPreviewBitmap;
        Bitmap oldLeica = leicaPreviewBitmap;
        sensorPreviewBitmap = null;
        leicaPreviewBitmap = null;
        if (oldSensor != null && !oldSensor.isRecycled()) oldSensor.recycle();
        if (oldLeica != null && !oldLeica.isRecycled()) oldLeica.recycle();
    }

    @Override
    protected void onDestroy() {
        clearPreviews();
        super.onDestroy();
    }
}
