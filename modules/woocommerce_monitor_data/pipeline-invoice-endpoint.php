<?php
/**
 * Pipeline Invoice Endpoint
 *
 * Add this to your WordPress theme's functions.php or create a micro-plugin.
 * Provides authenticated endpoints for the Pipeline WooCommerce Order Monitor:
 *   - Download invoice PDFs (requires WooCommerce PDF Invoices & Packing Slips)
 *   - Create manual orders for project invoicing
 *
 * Authentication uses the same monitor_secret_key as the bpost label endpoint.
 */

// Download invoice PDF for an order
add_action('wp_ajax_nopriv_pipeline_get_invoice', 'pipeline_get_invoice');
add_action('wp_ajax_pipeline_get_invoice', 'pipeline_get_invoice');

function pipeline_get_invoice() {
    $secret = isset($_GET['secret']) ? sanitize_text_field($_GET['secret']) : '';
    $stored_secret = get_option('bpost_monitor_secret_key', '');

    if (empty($stored_secret) || $secret !== $stored_secret) {
        wp_send_json_error('Unauthorized', 403);
    }

    $order_id = isset($_GET['order_id']) ? intval($_GET['order_id']) : 0;
    if (!$order_id) {
        wp_send_json_error('Missing order_id');
    }

    $order = wc_get_order($order_id);
    if (!$order) {
        wp_send_json_error('Order not found');
    }

    // Get invoice document via WCPDF
    if (!function_exists('wcpdf_get_document')) {
        wp_send_json_error('WooCommerce PDF Invoices & Packing Slips plugin not active');
    }

    $document = wcpdf_get_document('invoice', $order);

    if (!$document || !$document->exists()) {
        // Try to initialize the invoice if it doesn't exist yet
        $document = wcpdf_get_document('invoice', $order, true);
        if ($document) {
            $document->set_number(null); // Auto-assign next number
            $document->set_date(current_time('timestamp'));
            $document->save();
        }
    }

    if (!$document || !$document->exists()) {
        wp_send_json_error('Invoice not available for this order');
    }

    // Return invoice metadata as JSON (number, date) if requested
    if (isset($_GET['info_only'])) {
        $invoice_number = $document->get_number()->get_formatted();
        $invoice_date = $document->get_date()->date_i18n('Y-m-d');
        wp_send_json_success(array(
            'invoice_number' => $invoice_number,
            'invoice_date'   => $invoice_date,
            'order_id'       => $order_id,
        ));
    }

    // Generate and serve the PDF
    $pdf = $document->get_pdf();
    if (empty($pdf)) {
        wp_send_json_error('Failed to generate PDF');
    }

    $invoice_number = $document->get_number()->get_formatted();
    $filename = "Invoice_{$order_id}_{$invoice_number}.pdf";

    header('Content-Type: application/pdf');
    header('Content-Disposition: attachment; filename="' . $filename . '"');
    header('Content-Length: ' . strlen($pdf));
    echo $pdf;
    exit;
}

// Get invoice info (number, date) without downloading PDF
add_action('wp_ajax_nopriv_pipeline_get_invoice_info', 'pipeline_get_invoice_info');
add_action('wp_ajax_pipeline_get_invoice_info', 'pipeline_get_invoice_info');

function pipeline_get_invoice_info() {
    $_GET['info_only'] = true;
    pipeline_get_invoice();
}
