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
    private ImageView highlightPreviewView;
    private Bitmap sensorPreviewBitmap;
    private Bitmap leicaPreviewBitmap;
    private Bitmap highlightPreviewBitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic v0.5.2");
        title.setTextSize(22f);
        root.addView(title);

        TextView status = new TextView(this);
        String coreStatus = M10RColorSpecCore.selfCheckReport().replace(
                "Boundary: full Leica xy→temperature / NeutralToXY and RAW/DNG decoding are not wired in this diagnostic build.",
                "Boundary: ColorSpec self-check core only; RAW/DNG decoding and NeutralToXY are wired downstream.");
        status.setText(coreStatus +
                "\n\nv0.5.2 A/B diagnostic: frozen v0.4 sensor sanity + unchanged v0.5.1 Leica linear reference + one EXPERIMENTAL CA9 neutral-domain highlight-clipping candidate. The candidate is not firmware-parity claimed. MEDIUM tone and Differential Gamma remain disabled.");
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
        choose.setText("Choose M10-R DNG + Build v0.5.2 A/B References");
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
        leicaLabel.setText("v0.5.1 LEICA LINEAR REFERENCE (unchanged; headroom-preserving diagnostic)");
        leicaLabel.setTextSize(16f);
        leicaLabel.setPadding(0, pad / 2, 0, pad / 4);
        root.addView(leicaLabel);

        leicaPreviewView = new ImageView(this);
        leicaPreviewView.setAdjustViewBounds(true);
        leicaPreviewView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        leicaPreviewView.setContentDescription("v0.5.1 M10-R Leica linear reference preview");
        root.addView(leicaPreviewView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView highlightLabel = new TextView(this);
        highlightLabel.setText("v0.5.2 EXPERIMENTAL CA9 NEUTRAL-CLIP CANDIDATE (A/B only)");
        highlightLabel.setTextSize(16f);
        highlightLabel.setPadding(0, pad / 2, 0, pad / 4);
        root.addView(highlightLabel);

        highlightPreviewView = new ImageView(this);
        highlightPreviewView.setAdjustViewBounds(true);
        highlightPreviewView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        highlightPreviewView.setContentDescription("v0.5.2 experimental CA9 neutral clip preview");
        root.addView(highlightPreviewView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. This build preserves the validated v0.4 and v0.5.1 references and adds one isolated highlight-boundary experiment: DNG WhiteLevel clamp, then clipping in recovered CA9 gain/neutral space before the unchanged Leica ColorSpec transform. It is diagnostic only; MEDIUM tone and Differential Gamma remain disabled.");
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
        fileStatus.setText("Reading DNG and building frozen v0.4 + v0.5.1 + experimental v0.5.2 highlight A/B references…\n" + uri);
        new Thread(() -> parseDecodeAndRenderDng(uri), "m10r-dng-v052").start();
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
                final M10RNeutralClipReferenceRenderer.Result highlightPreview;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    sensorPreview = SensorPreviewCore.render(raw, info);
                    leicaPreview = M10RLinearReferenceRenderer.render(raw, info);
                    highlightPreview = M10RNeutralClipReferenceRenderer.render(raw, info);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nLEGACY NOTE: the decoder summary's RGGB parity names are diagnostic-only; actual CFA is resolved separately." +
                            "\n\nDECODER STATUS: PIXEL-EXACT CFA PRESERVED; frozen v0.4 + unchanged v0.5.1 + experimental v0.5.2 A/B BUILT.";
                } else {
                    sensorPreview = null;
                    leicaPreview = null;
                    highlightPreview = null;
                    rawDiagnostic = "Reference render not run: this diagnostic intentionally preserves the proven M10-R compression-7 path; compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic,
                        sensorPreview, leicaPreview, highlightPreview));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> {
                clearPreviews();
                fileStatus.setText("DNG v0.5.2 A/B render failed: " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
            });
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info,
                              String rawDiagnostic,
                              SensorPreviewCore.PreviewResult sensorPreview,
                              M10RLinearReferenceRenderer.Result leicaPreview,
                              M10RNeutralClipReferenceRenderer.Result highlightPreview) {
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
            leicaDiagnostic = "v0.5.1 Leica linear reference unavailable.";
        }

        String highlightDiagnostic;
        if (highlightPreview != null) {
            Bitmap next = Bitmap.createBitmap(highlightPreview.argb, highlightPreview.width,
                    highlightPreview.height, Bitmap.Config.ARGB_8888);
            Bitmap old = highlightPreviewBitmap;
            highlightPreviewBitmap = next;
            highlightPreviewView.setImageBitmap(next);
            if (old != null && old != next && !old.isRecycled()) old.recycle();
            highlightDiagnostic = highlightPreview.diagnosticSummary();
        } else {
            highlightDiagnostic = "v0.5.2 experimental highlight candidate unavailable.";
        }

        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\n" + sensorDiagnostic + "\n\n" + leicaDiagnostic +
                "\n\n" + highlightDiagnostic +
                "\n\nBoundary: v0.5.2 is an A/B diagnostic only. A visible improvement in the experimental image would isolate the missing highlight/saturation boundary; it would not by itself prove firmware parity. MEDIUM tone and Differential Gamma remain disabled.");
    }

    private void clearPreviews() {
        if (sensorPreviewView != null) sensorPreviewView.setImageDrawable(null);
        if (leicaPreviewView != null) leicaPreviewView.setImageDrawable(null);
        if (highlightPreviewView != null) highlightPreviewView.setImageDrawable(null);
        Bitmap oldSensor = sensorPreviewBitmap;
        Bitmap oldLeica = leicaPreviewBitmap;
        Bitmap oldHighlight = highlightPreviewBitmap;
        sensorPreviewBitmap = null;
        leicaPreviewBitmap = null;
        highlightPreviewBitmap = null;
        if (oldSensor != null && !oldSensor.isRecycled()) oldSensor.recycle();
        if (oldLeica != null && !oldLeica.isRecycled()) oldLeica.recycle();
        if (oldHighlight != null && !oldHighlight.isRecycled()) oldHighlight.recycle();
    }

    @Override
    protected void onDestroy() {
        clearPreviews();
        super.onDestroy();
    }
}
