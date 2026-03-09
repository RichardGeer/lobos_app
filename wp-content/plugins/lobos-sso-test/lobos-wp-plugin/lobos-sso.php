<?php
/**
 * Plugin Name: Lobos SSO Test (Configurable)
 * Description: Issues HS256 JWT and redirects to Lobos TEST app (no external libs).
 * Version: 0.5
 * Author: Paul
 */

if (!defined('ABSPATH'))
{
    exit;
}

class Lobos_SSO_Test_Plugin
{
    const DEFAULT_URL = 'http://lobos.foodinformed.com:8000/landing';
    const DEFAULT_SECRET = '5FqrSBGbnTwx1uJe05H65312mpuLNP8swfmQCdwCoOETIMy7KR5lMUS4ipXfZ5fT';
    const DEFAULT_ISSUER = 'wp-sim';

    const OPTION_URL = 'lobos_test_url';
    const OPTION_SECRET = 'lobos_test_jwt_secret';
    const OPTION_ISSUER = 'lobos_test_jwt_issuer';

    const SETTINGS_GROUP = 'lobos_test_sso_settings';
    const ADMIN_SLUG = 'lobos-test-sso';

    const SHORTCODE_BUTTON = 'lobos_test_button';
    const QUERY_ARG = 'lobos_test_sso';

    public function init()
    {
        add_action('admin_init', array($this, 'register_settings'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('template_redirect', array($this, 'handle_sso_redirect'));

        add_shortcode(self::SHORTCODE_BUTTON, array($this, 'button_shortcode'));
    }

    public function get_option_value($key, $default)
    {
        $value = get_option($key, null);

        if ($value === null || $value === '')
        {
            return $default;
        }

        return $value;
    }

    public function get_target_url()
    {
        return $this->get_option_value(self::OPTION_URL, self::DEFAULT_URL);
    }

    public function get_secret()
    {
        return $this->get_option_value(self::OPTION_SECRET, self::DEFAULT_SECRET);
    }

    public function get_issuer()
    {
        return $this->get_option_value(self::OPTION_ISSUER, self::DEFAULT_ISSUER);
    }

    public function b64url_encode($data)
    {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }

    public function jwt_hs256($payload, $secret)
    {
        $header = array(
            'alg' => 'HS256',
            'typ' => 'JWT',
        );

        $header_encoded = $this->b64url_encode(wp_json_encode($header));
        $payload_encoded = $this->b64url_encode(wp_json_encode($payload));
        $signature = hash_hmac('sha256', $header_encoded . '.' . $payload_encoded, $secret, true);
        $signature_encoded = $this->b64url_encode($signature);

        return $header_encoded . '.' . $payload_encoded . '.' . $signature_encoded;
    }

    public function register_settings()
    {
        register_setting(self::SETTINGS_GROUP, self::OPTION_URL);
        register_setting(self::SETTINGS_GROUP, self::OPTION_SECRET);
        register_setting(self::SETTINGS_GROUP, self::OPTION_ISSUER);
    }

    public function add_admin_menu()
    {
        add_options_page(
            'Lobos Test SSO Settings',
            'Lobos Test SSO',
            'manage_options',
            self::ADMIN_SLUG,
            array($this, 'settings_page')
        );
    }

    public function settings_page()
    {
        if (!current_user_can('manage_options'))
        {
            return;
        }
        ?>
        <div class="wrap">
            <h1>Lobos Test SSO Settings</h1>
            <form method="post" action="options.php">
                <?php settings_fields(self::SETTINGS_GROUP); ?>

                <table class="form-table">
                    <tr>
                        <th scope="row">Lobos Landing URL</th>
                        <td>
                            <input
                                type="text"
                                name="<?php echo esc_attr(self::OPTION_URL); ?>"
                                value="<?php echo esc_attr($this->get_target_url()); ?>"
                                style="width:400px;"
                            >
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">JWT Secret</th>
                        <td>
                            <input
                                type="text"
                                name="<?php echo esc_attr(self::OPTION_SECRET); ?>"
                                value="<?php echo esc_attr($this->get_secret()); ?>"
                                style="width:400px;"
                            >
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">JWT Issuer</th>
                        <td>
                            <input
                                type="text"
                                name="<?php echo esc_attr(self::OPTION_ISSUER); ?>"
                                value="<?php echo esc_attr($this->get_issuer()); ?>"
                                style="width:200px;"
                            >
                        </td>
                    </tr>
                </table>

                <?php submit_button(); ?>
            </form>

            <hr>

            <h2>Shortcode</h2>
            <p><code>[<?php echo esc_html(self::SHORTCODE_BUTTON); ?>]</code></p>
        </div>
        <?php
    }

    public function handle_sso_redirect()
    {
        if (!isset($_GET[self::QUERY_ARG]))
        {
            return;
        }

        if (!is_user_logged_in())
        {
            $redirect_to = add_query_arg(self::QUERY_ARG, '1', home_url('/'));
            wp_safe_redirect(wp_login_url($redirect_to));
            exit;
        }

        $user = wp_get_current_user();
        $now = time();

        $secret = $this->get_secret();
        $issuer = $this->get_issuer();
        $lobos_url = $this->get_target_url();

        $payload = array(
            'iss'        => $issuer,
            'sub'        => (string) $user->ID,
            'email'      => (string) $user->user_email,
            'first_name' => (string) $user->first_name,
            'last_name'  => (string) $user->last_name,
            'roles'      => is_array($user->roles) ? array_values($user->roles) : array(),
            'iat'        => $now,
            'exp'        => $now + 900,
        );

        $jwt = $this->jwt_hs256($payload, $secret);

        wp_redirect($lobos_url . '?token=' . urlencode($jwt));
        exit;
    }

    public function button_shortcode()
    {
        $url = esc_url(add_query_arg(self::QUERY_ARG, '1', home_url('/')));

        return '<a href="' . $url . '" style="display:inline-block;padding:12px 20px;font-size:16px;background:#222;color:#fff;text-decoration:none;border-radius:6px;">Open LOBOs Test</a>';
    }
}

function lobos_test_sso_boot_plugin()
{
    static $instance = null;

    if ($instance === null)
    {
        $instance = new Lobos_SSO_Test_Plugin();
        $instance->init();
    }

    return $instance;
}

lobos_test_sso_boot_plugin();