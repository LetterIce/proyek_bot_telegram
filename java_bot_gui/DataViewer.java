/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/GUIForms/JFrame.java to edit this template
 */
package java_bot_gui;

/**
 *
 * @author Admin
 */

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Vector;
import java.io.FileWriter;
import java.io.IOException;
import javax.swing.filechooser.FileNameExtensionFilter;

public class DataViewer extends javax.swing.JFrame {
    
    private static final java.util.logging.Logger logger = java.util.logging.Logger.getLogger(DataViewer.class.getName());
    private JTable table;
    private JScrollPane scrollPane;

    /**
     * Creates new form DataViewer
     */
    public DataViewer() {
        initComponents();
    }
    
    public DataViewer(UI parent, String dataType, String jsonData) {
        super("Data Viewer - " + dataType);
        setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE);
        setSize(700, 400);
        setLocationRelativeTo(parent);

        Vector<String> columns = new Vector<>();
        Vector<Vector<Object>> data = new Vector<>();

        try {
            if (jsonData.trim().startsWith("{")) {
                JSONObject obj = new JSONObject(jsonData);
                if (obj.has("history")) {
                    JSONArray arr = obj.getJSONArray("history");
                    columns = getColumns(arr, dataType);
                    data = UI.jsonToTableData(arr, columns);
                } else {
                    columns = getColumns(new JSONArray(), dataType);
                }
            } else {
                JSONArray arr = new JSONArray(jsonData);
                columns = getColumns(arr, dataType);
                data = UI.jsonToTableData(arr, columns);
            }
        } catch (Exception e) {
            columns.add("Error");
            Vector<Object> row = new Vector<>();
            row.add("Failed to parse data: " + e.getMessage());
            data.add(row);
        }

        DefaultTableModel model = new DefaultTableModel(data, columns);
        table = new JTable(model);
        scrollPane = new JScrollPane(table);

        getContentPane().setLayout(new BorderLayout());
        getContentPane().add(scrollPane, BorderLayout.CENTER);

        JButton closeBtn = new JButton("Close");
        closeBtn.addActionListener(e -> dispose());

        // Add Download CSV button
        JButton downloadCsvBtn = new JButton("Download CSV");
        downloadCsvBtn.addActionListener(e -> downloadTableToCSV());

        JPanel btnPanel = new JPanel();
        btnPanel.add(downloadCsvBtn);
        btnPanel.add(closeBtn);
        getContentPane().add(btnPanel, BorderLayout.SOUTH);
    }
    
    private Vector<String> getColumns(JSONArray arr, String dataType) {
        Vector<String> cols = new Vector<>();
        if (dataType.equalsIgnoreCase("History")) {
            cols.add("timestamp");
            cols.add("user_id");
            cols.add("message_text");
            cols.add("response_text");
            cols.add("message_type");
        } else if (dataType.equalsIgnoreCase("Members")) {
            cols.add("user_id");
            cols.add("first_name");
            cols.add("is_registered");
            cols.add("is_admin");
            cols.add("is_banned");
        } else if (dataType.equalsIgnoreCase("Keywords")) {
            cols.add("keyword");
            cols.add("response");
            cols.add("usage_count");
            cols.add("created_at");
        }
        // Try to auto-detect columns if array is not empty
        if (arr.length() > 0) {
            JSONObject obj = arr.getJSONObject(0);
            for (String key : obj.keySet()) {
                if (!cols.contains(key)) cols.add(key);
            }
        }
        return cols;
    }
    
    private void downloadTableToCSV() {
        JFileChooser fileChooser = new JFileChooser();
        fileChooser.setDialogTitle("Save as CSV");
        fileChooser.setFileFilter(new FileNameExtensionFilter("CSV Files", "csv"));
        int userSelection = fileChooser.showSaveDialog(this);
        if (userSelection == JFileChooser.APPROVE_OPTION) {
            java.io.File fileToSave = fileChooser.getSelectedFile();
            String filePath = fileToSave.getAbsolutePath();
            if (!filePath.toLowerCase().endsWith(".csv")) {
                filePath += ".csv";
            }
            try (FileWriter csvWriter = new FileWriter(filePath)) {
                DefaultTableModel model = (DefaultTableModel) table.getModel();
                // Write header
                for (int i = 0; i < model.getColumnCount(); i++) {
                    csvWriter.append(model.getColumnName(i));
                    if (i < model.getColumnCount() - 1) csvWriter.append(",");
                }
                csvWriter.append("\n");
                // Write rows
                for (int row = 0; row < model.getRowCount(); row++) {
                    for (int col = 0; col < model.getColumnCount(); col++) {
                        Object value = model.getValueAt(row, col);
                        String cell = value == null ? "" : value.toString();
                        // Remove emoji from cell value
                        cell = removeEmojis(cell);
                        cell = cell.replace("\"", "\"\"");
                        // Quote if contains comma or quote
                        if (cell.contains(",") || cell.contains("\"")) {
                            cell = "\"" + cell + "\"";
                        }
                        csvWriter.append(cell);
                        if (col < model.getColumnCount() - 1) csvWriter.append(",");
                    }
                    csvWriter.append("\n");
                }
                csvWriter.flush();
                JOptionPane.showMessageDialog(this, "Data berhasil disimpan ke " + filePath, "Sukses", JOptionPane.INFORMATION_MESSAGE);
            } catch (IOException ex) {
                JOptionPane.showMessageDialog(this, "Gagal menyimpan file: " + ex.getMessage(), "Error", JOptionPane.ERROR_MESSAGE);
            }
        }
    }
    
    private String removeEmojis(String input) {
        if (input == null) return "";
        // Remove most common emoji unicode blocks
        return input.replaceAll(
            "[\\p{InEmoticons}" +
            "\\p{InMiscellaneousSymbolsAndPictographs}" +
            "\\p{InTransportAndMapSymbols}" +
            "\\p{InSupplementalSymbolsAndPictographs}" +
            "\\p{InMiscellaneousSymbols}" +
            "\\p{InDingbats}" +
            "\\p{So}" + // Symbol, other
            "]+", "")
            // Remove some additional emoji ranges (fallback)
            .replaceAll("[\\x{1F600}-\\x{1F64F}]", "")
            .replaceAll("[\\x{1F300}-\\x{1F5FF}]", "")
            .replaceAll("[\\x{1F680}-\\x{1F6FF}]", "")
            .replaceAll("[\\x{2600}-\\x{26FF}]", "")
            .replaceAll("[\\x{2700}-\\x{27BF}]", "");
    }


    /**
     * This method is called from within the constructor to initialize the form.
     * WARNING: Do NOT modify this code. The content of this method is always
     * regenerated by the Form Editor.
     */
    @SuppressWarnings("unchecked")
    // <editor-fold defaultstate="collapsed" desc="Generated Code">                          
    private void initComponents() {

        setDefaultCloseOperation(javax.swing.WindowConstants.EXIT_ON_CLOSE);
        setTitle("Data viewer");

        javax.swing.GroupLayout layout = new javax.swing.GroupLayout(getContentPane());
        getContentPane().setLayout(layout);
        layout.setHorizontalGroup(
            layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGap(0, 400, Short.MAX_VALUE)
        );
        layout.setVerticalGroup(
            layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGap(0, 300, Short.MAX_VALUE)
        );

        pack();
    }// </editor-fold>                        

    /**
     * @param args the command line arguments
     */
    public static void main(String args[]) {
        /* Set the Nimbus look and feel */
        //<editor-fold defaultstate="collapsed" desc=" Look and feel setting code (optional) ">
        /* If Nimbus (introduced in Java SE 6) is not available, stay with the default look and feel.
         * For details see http://download.oracle.com/javase/tutorial/uiswing/lookandfeel/plaf.html 
         */
        try {
            for (javax.swing.UIManager.LookAndFeelInfo info : javax.swing.UIManager.getInstalledLookAndFeels()) {
                if ("Nimbus".equals(info.getName())) {
                    javax.swing.UIManager.setLookAndFeel(info.getClassName());
                    break;
                }
            }
        } catch (ReflectiveOperationException | javax.swing.UnsupportedLookAndFeelException ex) {
            logger.log(java.util.logging.Level.SEVERE, null, ex);
        }
        //</editor-fold>

        /* Create and display the form */
        java.awt.EventQueue.invokeLater(() -> new DataViewer().setVisible(true));
    }

    // Variables declaration - do not modify                     
    // End of variables declaration                   
}
