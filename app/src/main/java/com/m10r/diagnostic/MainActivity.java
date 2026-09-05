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
    private ImageView whiteClampPreviewView;
    private ImageView headroomNeutralPreviewView;
    private ImageView compositePreviewView;
    private Bitmap sensorPreviewBitmap;
    private Bitmap leicaPreviewBitmap;
    private Bitmap whiteClampPreviewBitmap;
    private Bitmap headroomNeutralPreviewBitmap;
    private Bitmap compositePreviewBitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic v0.5.3");
        title.setTextSize(22f);
        root.addView(title);

        TextView status = new TextView(this);
        String coreStatus = M10RColorSpecCore.selfCheckReport().replace(
                "Boundary: full Leica xy→temperature / NeutralToXY and RAW/DNG decoding are not wired in this diagnostic build.",
                "Boundary: ColorSpec self-check core only; RAW/DNG decoding and NeutralToXY are wired downstream.");
        status.setText(coreStatus +
                "\n\nv0.5.3 highlight factorial: frozen v0.4 sensor sanity + unchanged v0.5.1 headroom/no-neutral reference + WhiteLevel-clamp-only + headroom/neutral-clip-only + unchanged v0.5.2 composite. This separates the two variables changed together in v0.5.2. No candidate is firmware-parity claimed. MEDIUM tone and Differential Gamma remain disabled.");
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
        choose.setText("Choose M10-R DNG + Build v0.5.3 2x2 Highlight Test");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        TextView sensorLabel = addLabel(root, "v0.4 SENSOR SANITY (frozen)", pad);
        sensorPreviewView = addPreview(root, "v0.4 M10-R sensor sanity preview");

        addLabel(root, "A — v0.5.1 HEADROOM + NO NEUTRAL CLIP (unchanged reference)", pad);
        leicaPreviewView = addPreview(root, "A v0.5.1 headroom no-neutral reference");

        addLabel(root, "B — v0.5.3 WHITELIMIT CLAMP ONLY (no neutral clip)", pad);
        whiteClampPreviewView = addPreview(root, "B WhiteLevel clamp-only preview");

        addLabel(root, "C — v0.5.3 HEADROOM + CA9 NEUTRAL CLIP ONLY", pad);
        headroomNeutralPreviewView = addPreview(root, "C headroom plus neutral-clip preview");

        addLabel(root, "D — v0.5.2 WHITELIMIT + CA9 NEUTRAL CLIP (unchanged composite)", pad);
        compositePreviewView = addPreview(root, "D unchanged v0.5.2 composite preview");

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. The four ColorSpec images form a 2x2 test: A=headroom/no-neutral, B=WhiteLevel-clamp/no-neutral, C=headroom/neutral-clip, D=WhiteLevel-clamp/neutral-clip. This isolates which part of v0.5.2 removed the false highlight colors. Recovered firmware proves a direct 11-bit B2Y WB-gain path exists in parallel with ASN→CA9, but this build does not yet claim its exact arithmetic or stage order.");
        fileStatus.setPadding(0, pad / 2, 0, 0);
        fileStatus.setTextIsSelectable(true);
        root.addView(fileStatus);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
    }

    private TextView addLabel(LinearLayout root, String text, int pad) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(16f);
        label.setPadding(0, pad / 2, 0, pad / 4);
        root.addView(label);
        return label;
    }

    private ImageView addPreview(LinearLayout root, String description) {
        ImageView view = new ImageView(this);
        view.setAdjustViewBounds(true);
        view.setScaleType(ImageView.ScaleType.FIT_CENTER);
        view.setContentDescription(description);
        root.addView(view, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return view;
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
        fileStatus.setText("Reading DNG and building v0.5.3 2x2 highlight-boundary references…\n" + uri);
        new Thread(() -> parseDecodeAndRenderDng(uri), "m10r-dng-v053").start();
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
                final M10RHighlightFactorialRenderer.Result whiteClampPreview;
                final M10RHighlightFactorialRenderer.Result headroomNeutralPreview;
                final M10RNeutralClipReferenceRenderer.Result compositePreview;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    sensorPreview = SensorPreviewCore.render(raw, info);
                    leicaPreview = M10RLinearReferenceRenderer.render(raw, info);
                    whiteClampPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.WHITELEVEL_CLAMP_ONLY);
                    headroomNeutralPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.HEADROOM_NEUTRAL_CLIP_ONLY);
                    compositePreview = M10RNeutralClipReferenceRenderer.render(raw, info);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nLEGACY NOTE: the decoder summary's RGGB parity names are diagnostic-only; actual CFA is resolved separately." +
                            "\n\nDECODER STATUS: PIXEL-EXACT CFA PRESERVED; v0.5.3 2x2 HIGHLIGHT FACTORIAL BUILT.";
                } else {
                    sensorPreview = null;
                    leicaPreview = null;
                    whiteClampPreview = null;
                    headroomNeutralPreview = null;
                    compositePreview = null;
                    rawDiagnostic = "Reference render not run: this diagnostic intentionally preserves the proven M10-R compression-7 path; compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic, sensorPreview,
                        leicaPreview, whiteClampPreview, headroomNeutralPreview, compositePreview));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> {
                clearPreviews();
                fileStatus.setText("DNG v0.5.3 factorial render failed: " +
                        ex.getClass().getSimpleName() + ": " + ex.getMessage());
            });
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info,
                              String rawDiagnostic,
                              SensorPreviewCore.PreviewResult sensorPreview,
                              M10RLinearReferenceRenderer.Result leicaPreview,
                              M10RHighlightFactorialRenderer.Result whiteClampPreview,
                              M10RHighlightFactorialRenderer.Result headroomNeutralPreview,
                              M10RNeutralClipReferenceRenderer.Result compositePreview) {
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

        String sensorDiagnostic = setSensorPreview(sensorPreview);
        String leicaDiagnostic = setLinearPreview(leicaPreview);
        String whiteClampDiagnostic = setFactorialPreview(whiteClampPreviewView,
                whiteClampPreviewBitmap, whiteClampPreview, 0);
        if (whiteClampPreview != null) {
            whiteClampPreviewBitmap = bitmapFrom(whiteClampPreview.argb,
                    whiteClampPreview.width, whiteClampPreview.height, whiteClampPreviewView,
                    whiteClampPreviewBitmap);
        }
        String headroomNeutralDiagnostic;
        if (headroomNeutralPreview != null) {
            headroomNeutralPreviewBitmap = bitmapFrom(headroomNeutralPreview.argb,
                    headroomNeutralPreview.width, headroomNeutralPreview.height,
                    headroomNeutralPreviewView, headroomNeutralPreviewBitmap);
            headroomNeutralDiagnostic = headroomNeutralPreview.diagnosticSummary();
        } else {
            headroomNeutralDiagnostic = "C headroom + neutral-clip candidate unavailable.";
        }
        String compositeDiagnostic;
        if (compositePreview != null) {
            compositePreviewBitmap = bitmapFrom(compositePreview.argb, compositePreview.width,
                    compositePreview.height, compositePreviewView, compositePreviewBitmap);
            compositeDiagnostic = compositePreview.diagnosticSummary();
        } else {
            compositeDiagnostic = "D unchanged v0.5.2 composite unavailable.";
        }

        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\n" + sensorDiagnostic +
                "\n\nA — " + leicaDiagnostic +
                "\n\nB — " + whiteClampDiagnostic +
                "\n\nC — " + headroomNeutralDiagnostic +
                "\n\nD — " + compositeDiagnostic +
                "\n\nINTERPRETATION KEY: if B≈D visually, WhiteLevel clamp is dominant. If C≈D, CA9 neutral-domain clipping is dominant. If only D is clean, both are required. If B and C each partly improve A, both contribute. This is variable isolation only; exact Leica 11-bit front-end arithmetic/stage order remains to be recovered. MEDIUM tone and Differential Gamma remain disabled.");
    }

    private String setSensorPreview(SensorPreviewCore.PreviewResult preview) {
        if (preview == null) return "v0.4 sensor preview unavailable.";
        sensorPreviewBitmap = bitmapFrom(preview.argb, preview.width, preview.height,
                sensorPreviewView, sensorPreviewBitmap);
        return preview.diagnosticSummary();
    }

    private String setLinearPreview(M10RLinearReferenceRenderer.Result preview) {
        if (preview == null) return "v0.5.1 Leica linear reference unavailable.";
        leicaPreviewBitmap = bitmapFrom(preview.argb, preview.width, preview.height,
                leicaPreviewView, leicaPreviewBitmap);
        return preview.diagnosticSummary();
    }

    private String setFactorialPreview(ImageView view, Bitmap old,
                                       M10RHighlightFactorialRenderer.Result preview,
                                       int ignored) {
        if (preview == null) return "B WhiteLevel-clamp-only candidate unavailable.";
        return preview.diagnosticSummary();
    }

    private Bitmap bitmapFrom(int[] argb, int width, int height, ImageView view, Bitmap old) {
        Bitmap next = Bitmap.createBitmap(argb, width, height, Bitmap.Config.ARGB_8888);
        view.setImageBitmap(next);
        if (old != null && old != next && !old.isRecycled()) old.recycle();
        return next;
    }

    private void clearPreviews() {
        if (sensorPreviewView != null) sensorPreviewView.setImageDrawable(null);
        if (leicaPreviewView != null) leicaPreviewView.setImageDrawable(null);
        if (whiteClampPreviewView != null) whiteClampPreviewView.setImageDrawable(null);
        if (headroomNeutralPreviewView != null) headroomNeutralPreviewView.setImageDrawable(null);
        if (compositePreviewView != null) compositePreviewView.setImageDrawable(null);
        recycle(sensorPreviewBitmap);
        recycle(leicaPreviewBitmap);
        recycle(whiteClampPreviewBitmap);
        recycle(headroomNeutralPreviewBitmap);
        recycle(compositePreviewBitmap);
        sensorPreviewBitmap = null;
        leicaPreviewBitmap = null;
        whiteClampPreviewBitmap = null;
        headroomNeutralPreviewBitmap = null;
        compositePreviewBitmap = null;
    }

    private static void recycle(Bitmap bitmap) {
        if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
    }

    @Override
    protected void onDestroy() {
        clearPreviews();
        super.onDestroy();
    }
}
