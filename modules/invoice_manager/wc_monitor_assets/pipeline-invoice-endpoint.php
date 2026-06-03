<?php
/**
 * Pipeline Invoice Endpoint
 *
 * Add this to your WordPress theme's functions.php or create a micro-plugin.
 * Provides an authenticated endpoint for the Pipeline WooCommerce Order Monitor
 * to download invoice PDFs (requires WooCommerce PDF Invoices & Packing Slips).
 *
 * Authentication uses the BPOST_MONITOR_SECRET_KEY constant.
 * Define it in wp-config.php or your theme:
 *   define('BPOST_MONITOR_SECRET_KEY', 'your-secret-key-here');
 */

add_action('wp_ajax_nopriv_pipeline_get_invoice', 'pipeline_get_invoice');
add_action('wp_ajax_pipeline_get_invoice', 'pipeline_get_invoice');

function pipeline_get_invoice() {
    $secret = isset($_GET['secret']) ? sanitize_text_field($_GET['secret']) : '';

    if (!defined('BPOST_MONITOR_SECRET_KEY') || $secret !== BPOST_MONITOR_SECRET_KEY) {
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

    if (!function_exists('wcpdf_get_document')) {
        wp_send_json_error('WooCommerce PDF Invoices & Packing Slips plugin not active');
    }

    $document = wcpdf_get_document('invoice', $order);

    // Create the invoice if it doesn't exist yet
    if (!$document || !$document->exists()) {
        $document = wcpdf_get_document('invoice', $order, true);
        if ($document) {
            $document->set_number(null);
            $document->set_date(current_time('timestamp'));
            $document->save();
        }
    }

    if (!$document || !$document->exists()) {
        wp_send_json_error('Invoice not available for this order');
    }

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
