package com.m10r.diagnostic;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.widget.Button;
import android.widget.EditText;
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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("M10-R RAW Diagnostic v0.3");
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
        choose.setText("Choose M10-R DNG + Decode CFA");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. v0.3 parses Leica DNG metadata and pixel-exact decodes compression-7 SOF3 CFA data; demosaic remains intentionally disabled.");
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
        fileStatus.setText("Reading DNG metadata and decoding lossless-JPEG CFA…\n" + uri);
        new Thread(() -> parseAndDecodeDng(uri), "m10r-dng-raw").start();
    }

    private void parseAndDecodeDng(Uri uri) {
        try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
            if (pfd == null) throw new IllegalStateException("content provider returned no file descriptor");
            try (FileInputStream in = new FileInputStream(pfd.getFileDescriptor());
                 FileChannel channel = in.getChannel()) {
                DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
                final String rawDiagnostic;
                if (info.isLosslessJpeg()) {
                    DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
                    rawDiagnostic = raw.diagnosticSummary() +
                            "\n\nDECODER STATUS: PIXELS DECODED. Next seam is black/white normalization + Bayer demosaic.";
                } else if (info.compression == 1) {
                    rawDiagnostic = "RAW decode not run: this file is uncompressed CFA; v0.3 currently targets the proven M10-R compression-7 path.";
                } else {
                    rawDiagnostic = "RAW decode not run: unsupported compression=" + info.compression + ".";
                }
                runOnUiThread(() -> applyDngInfo(uri, info, rawDiagnostic));
            }
        } catch (Throwable ex) {
            runOnUiThread(() -> fileStatus.setText("DNG RAW decode failed: " + ex.getClass().getSimpleName() + ": " + ex.getMessage()));
        }
    }

    private void applyDngInfo(Uri uri, DngMetadataReader.DngInfo info, String rawDiagnostic) {
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
        fileStatus.setText("Selected: " + uri + "\n\n" + info.summary() + "\n\n" + rawDiagnostic +
                "\n\nBoundary: v0.3 decodes the Bayer CFA exactly but does not yet demosaic or render it.");
    }
}
