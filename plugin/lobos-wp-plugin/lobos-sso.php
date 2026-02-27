<?php
/**
 * Plugin Name: Lobos SSO Test (Configurable)
 * Description: Issues HS256 JWT and redirects to Lobos app (no external libs).
 * Version: 0.4
 */

if (!defined('ABSPATH')) { exit; }

/* ===============================
   Default values (used on first install)
   =============================== */

define('LOBOS_DEFAULT_URL', 'http://lobos.foodinformed.com:8000/landing');
define('LOBOS_DEFAULT_SECRET', '5FqrSBGbnTwx1uJe05H65312mpuLNP8swfmQCdwCoOETIMy7KR5lMUS4ipXfZ5fT');
define('LOBOS_DEFAULT_ISSUER', 'wp-sim');

/* ===============================
   Helpers
   =============================== */

function lobos_b64url_encode($data) {
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

function lobos_jwt_hs256($payload, $secret) {
    $header = ['alg' => 'HS256', 'typ' => 'JWT'];
    $h = lobos_b64url_encode(json_encode($header));
    $p = lobos_b64url_encode(json_encode($payload));
    $sig = hash_hmac('sha256', $h . '.' . $p, $secret, true);
    $s = lobos_b64url_encode($sig);
    return $h . '.' . $p . '.' . $s;
}

/* ===============================
   Settings Registration
   =============================== */

add_action('admin_init', function () {
    register_setting('lobos_sso_settings', 'lobos_lobos_url');
    register_setting('lobos_sso_settings', 'lobos_jwt_secret');
    register_setting('lobos_sso_settings', 'lobos_jwt_issuer');
});

/* ===============================
   Admin Menu
   =============================== */

add_action('admin_menu', function () {
    add_options_page(
        'Lobos SSO Settings',
        'Lobos SSO',
        'manage_options',
        'lobos-sso',
        'lobos_sso_settings_page'
    );
});

function lobos_sso_settings_page() {
    ?>
    <div class="wrap">
        <h1>Lobos SSO Settings</h1>
        <form method="post" action="options.php">
            <?php settings_fields('lobos_sso_settings'); ?>
            <?php do_settings_sections('lobos_sso_settings'); ?>

            <table class="form-table">
                <tr>
                    <th>Lobos Landing URL</th>
                    <td>
                        <input type="text" name="lobos_lobos_url"
                            value="<?php echo esc_attr(get_option('lobos_lobos_url', LOBOS_DEFAULT_URL)); ?>"
                            style="width:400px;">
                    </td>
                </tr>
                <tr>
                    <th>JWT Secret</th>
                    <td>
                        <input type="text" name="lobos_jwt_secret"
                            value="<?php echo esc_attr(get_option('lobos_jwt_secret', LOBOS_DEFAULT_SECRET)); ?>"
                            style="width:400px;">
                    </td>
                </tr>
                <tr>
                    <th>JWT Issuer</th>
                    <td>
                        <input type="text" name="lobos_jwt_issuer"
                            value="<?php echo esc_attr(get_option('lobos_jwt_issuer', LOBOS_DEFAULT_ISSUER)); ?>"
                            style="width:200px;">
                    </td>
                </tr>
            </table>

            <?php submit_button(); ?>
        </form>
    </div>
    <?php
}

/* ===============================
   SSO Redirect Logic
   =============================== */

add_action('template_redirect', function () {

    if (!isset($_GET['lobos_sso'])) return;

    if (!is_user_logged_in()) {
        $redirect_to = add_query_arg('lobos_sso', '1', home_url('/'));
        wp_safe_redirect(wp_login_url($redirect_to));
        exit;
    }

    $user = wp_get_current_user();
    $now = time();

    $secret = get_option('lobos_jwt_secret', LOBOS_DEFAULT_SECRET);
    $issuer = get_option('lobos_jwt_issuer', LOBOS_DEFAULT_ISSUER);
    $lobos_url = get_option('lobos_lobos_url', LOBOS_DEFAULT_URL);

    $payload = [
        'iss' => $issuer,
        'sub' => (string)$user->ID,
        'email' => $user->user_email,
        'first_name' => $user->first_name,
        'last_name' => $user->last_name,
        'roles' => $user->roles,
        'iat' => $now,
        'exp' => $now + 900,
    ];

    $jwt = lobos_jwt_hs256($payload, $secret);
    wp_redirect($lobos_url . '?token=' . urlencode($jwt));
    exit;
});

/* ===============================
   Shortcode Button
   =============================== */

add_shortcode('lobos_button', function () {
    $url = esc_url(add_query_arg('lobos_sso', '1', home_url('/')));
    return '<a href="' . $url . '" style="display:inline-block;padding:12px 20px;font-size:16px;background:#222;color:#fff;text-decoration:none;border-radius:6px;">Open LOBOs</a>';
});