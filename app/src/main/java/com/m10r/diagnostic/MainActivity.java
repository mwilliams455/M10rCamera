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
    private ImageView aPreviewView;
    private ImageView bPreviewView;
    private ImageView cPreviewView;
    private ImageView dPreviewView;
    private Bitmap sensorPreviewBitmap;
    private Bitmap aPreviewBitmap;
    private Bitmap bPreviewBitmap;
    private Bitmap cPreviewBitmap;
    private Bitmap dPreviewBitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic — RENDER_PARITY1A");
        title.setTextSize(22f);
        root.addView(title);

        TextView status = new TextView(this);
        String coreStatus = M10RColorSpecCore.selfCheckReport().replace(
                "Boundary: full Leica xy→temperature / NeutralToXY and RAW/DNG decoding are not wired in this diagnostic build.",
                "Boundary: ColorSpec self-check core only; RAW/DNG decoding and NeutralToXY are wired downstream.");
        status.setText(coreStatus +
                "\n\nRENDER_PARITY1A canonical 2x2 highlight experiment. Only RAW headroom retention and the CA9 neutral-domain clipping candidate vary. CFA, demosaic, DNG black/white metadata, NeutralToXY/ColorSpec, output matrix and display encoding remain unchanged. No candidate is firmware-parity claimed. MEDIUM tone and Differential Gamma remain disabled.");
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
        choose.setText("Choose M10-R DNG + Build Canonical A/B/C/D Test");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        addLabel(root, "v0.4 SENSOR SANITY (frozen)", pad);
        sensorPreviewView = addPreview(root, "v0.4 M10-R sensor sanity preview");

        addLabel(root, "A — BASELINE: RAW HEADROOM OFF / CA9 CLIP OFF", pad);
        aPreviewView = addPreview(root, "A baseline: raw headroom off, CA9 clip off");

        addLabel(root, "B — RAW HEADROOM ON / CA9 CLIP OFF", pad);
        bPreviewView = addPreview(root, "B raw headroom on, CA9 clip off");

        addLabel(root, "C — RAW HEADROOM OFF / CA9 CLIP ON", pad);
        cPreviewView = addPreview(root, "C raw headroom off, CA9 clip on");

        addLabel(root, "D — RAW HEADROOM ON / CA9 CLIP ON", pad);
        dPreviewView = addPreview(root, "D raw headroom on, CA9 clip on");

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. Canonical RENDER_PARITY1A matrix: A=headroom OFF/CA9 OFF, B=headroom ON/CA9 OFF, C=headroom OFF/CA9 ON, D=headroom ON/CA9 ON. A↔B and C↔D isolate RAW headroom; A↔C and B↔D isolate CA9 clipping. This is controlled variable isolation only; exact Leica integer arithmetic and stage order remain to be recovered.");
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
        fileStatus.setText("Reading DNG and building canonical RENDER_PARITY1A references…\n" + uri);
        new Thread(() -> parseDecodeAndRenderDng(uri), "m10r-render-parity1a").start();
    }

    private void parseDecodeAndRenderDng(Uri uri) {
        try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
            if (pfd == null) throw new IllegalStateException("content provider returned no file descriptor");
            try (FileInputStream in = new FileInputStream(pfd.getFileDescriptor());
                 FileChannel channel = in.getChannel()) {
                DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
                final String rawDiagnostic;
                final SensorPreviewCore.PreviewResult sensorPreview;
                final M10RHighlightFactorialRenderer.Result aPreview;
                final M10RHighlightFactorialRenderer.Result bPreview;
                final M10RHighlightFactorialRenderer.Result cPreview;
                final M10RHighlightFactorialRenderer.Result dPreview;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    sensorPreview = SensorPreviewCore.render(raw, info);
                    aPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.A_BASELINE);
                    bPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.B_HEADROOM);
                    cPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP);
                    dPreview = M10RHighlightFactorialRenderer.render(raw, info,
                            M10RHighlightFactorialRenderer.Mode.D_HEADROOM_CA9);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nLEGACY NOTE: the decoder summary's RGGB parity names are diagnostic-only; actual CFA is resolved separately." +
                            "\n\nDECODER STATUS: PIXEL-EXACT CFA PRESERVED; RENDER_PARITY1A CANONICAL A/B/C/D BUILT.";
                } else {
                    sensorPreview = null;
                    aPreview = null;
                    bPreview = null;
                    cPreview = null;
                    dPreview = null;
                    rawDiagnostic = "Reference render not run: this diagnostic intentionally preserves the proven M10-R compression-7 path; compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic, sensorPreview,
                        aPreview, bPreview, cPreview, dPreview));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> {
                clearPreviews();
                fileStatus.setText("RENDER_PARITY1A render failed: " +
                        ex.getClass().getSimpleName() + ": " + ex.getMessage());
            });
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info,
                              String rawDiagnostic,
                              SensorPreviewCore.PreviewResult sensorPreview,
                              M10RHighlightFactorialRenderer.Result aPreview,
                              M10RHighlightFactorialRenderer.Result bPreview,
                              M10RHighlightFactorialRenderer.Result cPreview,
                              M10RHighlightFactorialRenderer.Result dPreview) {
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
        String aDiagnostic = setFactorialPreview(aPreviewView, aPreview, 'A');
        String bDiagnostic = setFactorialPreview(bPreviewView, bPreview, 'B');
        String cDiagnostic = setFactorialPreview(cPreviewView, cPreview, 'C');
        String dDiagnostic = setFactorialPreview(dPreviewView, dPreview, 'D');

        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\n" + sensorDiagnostic +
                "\n\nA — " + aDiagnostic +
                "\n\nB — " + bDiagnostic +
                "\n\nC — " + cDiagnostic +
                "\n\nD — " + dDiagnostic +
                "\n\nINTERPRETATION KEY: A↔B and C↔D isolate RAW headroom. A↔C and B↔D isolate CA9 neutral clipping. A↔D shows the combined effect. If both factors are near zero, neither belongs. If one produces coherent highlight-only changes while the other is near zero, isolate that mechanism. If D contains a meaningful interaction beyond the independent effects, the combined mechanism matters. This is variable isolation only; exact Leica integer arithmetic/stage order remains to be recovered. MEDIUM tone and Differential Gamma remain disabled.");
    }

    private String setSensorPreview(SensorPreviewCore.PreviewResult preview) {
        if (preview == null) return "v0.4 sensor preview unavailable.";
        sensorPreviewBitmap = bitmapFrom(preview.argb, preview.width, preview.height,
                sensorPreviewView, sensorPreviewBitmap);
        return preview.diagnosticSummary();
    }

    private String setFactorialPreview(ImageView view,
                                       M10RHighlightFactorialRenderer.Result preview,
                                       char label) {
        if (preview == null) return label + " canonical factorial candidate unavailable.";
        Bitmap old;
        switch (label) {
            case 'A': old = aPreviewBitmap; break;
            case 'B': old = bPreviewBitmap; break;
            case 'C': old = cPreviewBitmap; break;
            case 'D': old = dPreviewBitmap; break;
            default: throw new IllegalArgumentException("unknown factorial label " + label);
        }
        Bitmap next = bitmapFrom(preview.argb, preview.width, preview.height, view, old);
        switch (label) {
            case 'A': aPreviewBitmap = next; break;
            case 'B': bPreviewBitmap = next; break;
            case 'C': cPreviewBitmap = next; break;
            case 'D': dPreviewBitmap = next; break;
            default: break;
        }
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
        if (aPreviewView != null) aPreviewView.setImageDrawable(null);
        if (bPreviewView != null) bPreviewView.setImageDrawable(null);
        if (cPreviewView != null) cPreviewView.setImageDrawable(null);
        if (dPreviewView != null) dPreviewView.setImageDrawable(null);
        recycle(sensorPreviewBitmap);
        recycle(aPreviewBitmap);
        recycle(bPreviewBitmap);
        recycle(cPreviewBitmap);
        recycle(dPreviewBitmap);
        sensorPreviewBitmap = null;
        aPreviewBitmap = null;
        bPreviewBitmap = null;
        cPreviewBitmap = null;
        dPreviewBitmap = null;
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
