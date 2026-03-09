<?php
/**
 * Plugin Name: Lobos SSO Dev (Configurable)
 * Description: Issues HS256 JWT and redirects to Lobos DEV app (no external libs).
 * Version: 0.3
 */

if (!defined('ABSPATH')) { exit; }

/* ===============================
   Default values (used on first install)
   =============================== */

define('LOBOS_DEV_DEFAULT_URL', 'http://my.glp.com:8000/landing');
define('LOBOS_DEV_DEFAULT_SECRET', '5FqrSBGbnTwx1uJe05H65312mpuLNP8swfmQCdwCoOETIMy7KR5lMUS4ipXfZ5fT');
define('LOBOS_DEV_DEFAULT_ISSUER', 'wp-sim');

/* ===============================
   Helpers
   =============================== */

function lobos_dev_b64url_encode($data) {
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

function lobos_dev_jwt_hs256($payload, $secret) {
    $header = ['alg' => 'HS256', 'typ' => 'JWT'];

    $header_b64 = lobos_dev_b64url_encode(wp_json_encode($header));
    $payload_b64 = lobos_dev_b64url_encode(wp_json_encode($payload));

    $signature = hash_hmac('sha256', $header_b64 . '.' . $payload_b64, $secret, true);
    $signature_b64 = lobos_dev_b64url_encode($signature);

    return $header_b64 . '.' . $payload_b64 . '.' . $signature_b64;
}

/* ===============================
   Settings
   =============================== */

function lobos_dev_get_option($key, $default = '') {
    $opts = get_option('lobos_dev_sso_options', []);
    return isset($opts[$key]) ? $opts[$key] : $default;
}

function lobos_dev_get_target_url() {
    return lobos_dev_get_option('target_url', LOBOS_DEV_DEFAULT_URL);
}

function lobos_dev_get_secret() {
    return lobos_dev_get_option('jwt_secret', LOBOS_DEV_DEFAULT_SECRET);
}

function lobos_dev_get_issuer() {
    return lobos_dev_get_option('jwt_issuer', LOBOS_DEV_DEFAULT_ISSUER);
}

/* ===============================
   MemberPress helpers
   =============================== */

function lobos_dev_get_memberpress_memberships($user_id) {
    $result = [
        'user_id' => (int)$user_id,
        'exists' => false,
        'active_memberships' => [],
    ];

    if (!class_exists('MeprUser')) {
        return $result;
    }

    try {
        $mepr_user = new MeprUser($user_id);

        if (empty($mepr_user) || empty($mepr_user->ID)) {
            return $result;
        }

        $result['exists'] = true;

        $product_ids = $mepr_user->active_product_subscriptions('ids');

        if (!empty($product_ids) && is_array($product_ids)) {
            foreach ($product_ids as $product_id) {
                $product_id = (int)$product_id;
                $post = get_post($product_id);

                if ($post && !empty($post->post_title)) {
                    $result['active_memberships'][] = [
                        'id' => $product_id,
                        'title' => $post->post_title,
                    ];
                } else {
                    $result['active_memberships'][] = [
                        'id' => $product_id,
                        'title' => '',
                    ];
                }
            }
        }
    } catch (Exception $e) {
        // fail-safe
    }

    return $result;
}

/* ===============================
   Build user identity payload
   =============================== */

function lobos_dev_build_identity($user) {
    return [
        'email' => $user->user_email,
        'first_name' => get_user_meta($user->ID, 'first_name', true),
        'last_name' => get_user_meta($user->ID, 'last_name', true),
        'roles' => array_values((array)$user->roles),
        'membership' => [
            'memberpress' => lobos_dev_get_memberpress_memberships($user->ID),
        ],
    ];
}

/* ===============================
   Shortcode button
   Supports:
   [lobos_dev_button]
   [lobos_dev_sso_button]
   =============================== */

function lobos_dev_sso_button_shortcode($atts) {
    if (!is_user_logged_in()) {
        return '<a href="' . esc_url(wp_login_url(get_permalink())) . '">Log in to continue</a>';
    }

    $atts = shortcode_atts([
        'text' => 'Open Lobos Dev',
    ], $atts, 'lobos_dev_button');

    $url = add_query_arg('lobos_dev_sso', '1', home_url('/'));

    return '<a class="button" href="' . esc_url($url) . '">' . esc_html($atts['text']) . '</a>';
}

add_shortcode('lobos_dev_button', 'lobos_dev_sso_button_shortcode');

/* ===============================
   Handle redirect with JWT
   =============================== */

function lobos_dev_handle_sso_redirect() {
    if (!isset($_GET['lobos_dev_sso']) || $_GET['lobos_dev_sso'] !== '1') {
        return;
    }

    if (!is_user_logged_in()) {
        auth_redirect();
    }

    $user = wp_get_current_user();
    if (!$user || empty($user->ID)) {
        wp_die('Unable to load current user.');
    }

    $target_url = lobos_dev_get_target_url();
    $secret = lobos_dev_get_secret();
    $issuer = lobos_dev_get_issuer();

    if (empty($target_url) || empty($secret) || empty($issuer)) {
        wp_die('Lobos Dev SSO is not configured correctly.');
    }

    $now = time();

    $payload = [
        'sub' => (string)$user->ID,
        'email' => $user->user_email,
        'first_name' => get_user_meta($user->ID, 'first_name', true),
        'last_name' => get_user_meta($user->ID, 'last_name', true),
        'roles' => array_values((array)$user->roles),
        'identity' => lobos_dev_build_identity($user),
        'iat' => $now,
        'exp' => $now + 3600,
        'iss' => $issuer,
    ];

    $jwt = lobos_dev_jwt_hs256($payload, $secret);

    $redirect_url = add_query_arg('token', rawurlencode($jwt), $target_url);
    wp_redirect($redirect_url);
    exit;
}
add_action('init', 'lobos_dev_handle_sso_redirect');

/* ===============================
   Debug endpoint
   Visit:
   /?lobos_dev_me=1
   while logged in
   =============================== */

function lobos_dev_handle_debug_me() {
    if (!isset($_GET['lobos_dev_me']) || $_GET['lobos_dev_me'] !== '1') {
        return;
    }

    if (!is_user_logged_in()) {
        wp_send_json([
            'error' => 'not_logged_in',
        ], 401);
    }

    $user = wp_get_current_user();
    if (!$user || empty($user->ID)) {
        wp_send_json([
            'error' => 'unable_to_load_user',
        ], 500);
    }

    $data = [
        'user_id' => (string)$user->ID,
        'identity' => lobos_dev_build_identity($user),
    ];

    wp_send_json($data, 200);
}
add_action('init', 'lobos_dev_handle_debug_me');

/* ===============================
   Admin settings
   =============================== */

function lobos_dev_register_settings() {
    register_setting('lobos_dev_sso_group', 'lobos_dev_sso_options');

    add_settings_section(
        'lobos_dev_sso_main',
        'Lobos Dev SSO Settings',
        '__return_false',
        'lobos-dev-sso'
    );

    add_settings_field(
        'target_url',
        'Target URL',
        'lobos_dev_target_url_field',
        'lobos-dev-sso',
        'lobos_dev_sso_main'
    );

    add_settings_field(
        'jwt_secret',
        'JWT Secret',
        'lobos_dev_jwt_secret_field',
        'lobos-dev-sso',
        'lobos_dev_sso_main'
    );

    add_settings_field(
        'jwt_issuer',
        'JWT Issuer',
        'lobos_dev_jwt_issuer_field',
        'lobos-dev-sso',
        'lobos_dev_sso_main'
    );
}
add_action('admin_init', 'lobos_dev_register_settings');

function lobos_dev_target_url_field() {
    $value = esc_attr(lobos_dev_get_target_url());
    echo '<input type="text" name="lobos_dev_sso_options[target_url]" value="' . $value . '" class="regular-text" />';
}

function lobos_dev_jwt_secret_field() {
    $value = esc_attr(lobos_dev_get_secret());
    echo '<input type="text" name="lobos_dev_sso_options[jwt_secret]" value="' . $value . '" class="regular-text" />';
}

function lobos_dev_jwt_issuer_field() {
    $value = esc_attr(lobos_dev_get_issuer());
    echo '<input type="text" name="lobos_dev_sso_options[jwt_issuer]" value="' . $value . '" class="regular-text" />';
}

function lobos_dev_add_admin_menu() {
    add_options_page(
        'Lobos Dev SSO',
        'Lobos Dev SSO',
        'manage_options',
        'lobos-dev-sso',
        'lobos_dev_render_settings_page'
    );
}
add_action('admin_menu', 'lobos_dev_add_admin_menu');

function lobos_dev_render_settings_page() {
    ?>
    <div class="wrap">
        <h1>Lobos Dev SSO</h1>
        <form method="post" action="options.php">
            <?php
            settings_fields('lobos_dev_sso_group');
            do_settings_sections('lobos-dev-sso');
            submit_button();
            ?>
        </form>

        <hr>

        <p><strong>Debug endpoint:</strong> <code><?php echo esc_html(home_url('/?lobos_dev_me=1')); ?></code></p>
        <p><strong>SSO trigger:</strong> <code><?php echo esc_html(home_url('/?lobos_dev_sso=1')); ?></code></p>
        <p><strong>Shortcodes:</strong> <code>[lobos_dev_button]</code> or <code>[lobos_dev_sso_button]</code></p>
    </div>
    <?php
}