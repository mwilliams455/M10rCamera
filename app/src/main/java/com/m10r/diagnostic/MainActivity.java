package com.m10r.diagnostic;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

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
        title.setText("M10-R ColorSpec Diagnostic v0.1");
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
        choose.setText("Choose M10-R DNG");
        choose.setOnClickListener(v -> chooseDng());
        root.addView(choose);

        fileStatus = new TextView(this);
        fileStatus.setText("No DNG selected. v0.1 validates the Leica core; RAW decode is the next seam.");
        fileStatus.setPadding(0, pad / 2, 0, 0);
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
            int[] gains = M10RColorSpecCore.recoverCa9Gains(neutral);
            double[] rebuilt = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
            result.setText(String.format(Locale.US,
                    "CA9 gains = [%d, %d, %d]\nFirmware neutral = [%.10f, %.10f, %.10f]",
                    gains[0], gains[1], gains[2], rebuilt[0], rebuilt[1], rebuilt[2]));
        } catch (RuntimeException ex) {
            result.setText("Input error: " + ex.getMessage());
        }
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
            // Some providers grant only the transient read permission; the diagnostic can still report the URI.
        }
        fileStatus.setText("Selected: " + uri + "\nDNG decode/render is intentionally not active in v0.1.");
    }
}
