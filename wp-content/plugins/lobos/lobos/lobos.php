<?php
/**
 * Plugin Name: Lobos Dev
 * Description: Lobos DEV SSO plugin with button shortcode, debug shortcode, JWT redirect, membership check, and admin settings.
 * Version: 0.7
 * Author: Paul
 */

if (!defined('ABSPATH'))
{
    exit;
}

class GLP_Lobos_Dev_Plugin
{
    const DEFAULT_URL = 'http://my.glp.com:8000/landing';
    const DEFAULT_SECRET = '5FqrSBGbnTwx1uJe05H65312mpuLNP8swfmQCdwCoOETIMy7KR5lMUS4ipXfZ5fT';
    const DEFAULT_ISSUER = 'wp-sim';
    const DEFAULT_BUTTON_TEXT = 'Open Lobos Dev';
    const DEFAULT_REQUIRE_MEMBERSHIP = '0';

    const OPTION_TARGET_URL = 'glp_lobos_dev_target_url';
    const OPTION_SECRET = 'glp_lobos_dev_secret';
    const OPTION_ISSUER = 'glp_lobos_dev_issuer';
    const OPTION_BUTTON_TEXT = 'glp_lobos_dev_button_text';
    const OPTION_REQUIRE_MEMBERSHIP = 'glp_lobos_dev_require_membership';

    const SETTINGS_GROUP = 'glp_lobos_dev_settings_group';
    const ADMIN_SLUG = 'glp-lobos-dev-settings';

    const SHORTCODE_BUTTON = 'lobos_dev_button';
    const SHORTCODE_DEBUG = 'lobos_dev_debug';

    const ACTION_LAUNCH = 'glp_lobos_dev_launch';

    public function init()
    {
        add_shortcode(self::SHORTCODE_BUTTON, array($this, 'button_shortcode'));
        add_shortcode(self::SHORTCODE_DEBUG, array($this, 'debug_shortcode'));

        add_action('admin_post_' . self::ACTION_LAUNCH, array($this, 'handle_launch'));
        add_action('admin_post_nopriv_' . self::ACTION_LAUNCH, array($this, 'handle_launch'));

        add_action('admin_init', array($this, 'register_settings'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('wp_head', array($this, 'button_styles'));
    }

    public function get_option($key, $default = '')
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
        return $this->get_option(self::OPTION_TARGET_URL, self::DEFAULT_URL);
    }

    public function get_secret()
    {
        return $this->get_option(self::OPTION_SECRET, self::DEFAULT_SECRET);
    }

    public function get_issuer()
    {
        return $this->get_option(self::OPTION_ISSUER, self::DEFAULT_ISSUER);
    }

    public function get_button_text()
    {
        return $this->get_option(self::OPTION_BUTTON_TEXT, self::DEFAULT_BUTTON_TEXT);
    }

    public function get_require_membership()
    {
        return $this->get_option(self::OPTION_REQUIRE_MEMBERSHIP, self::DEFAULT_REQUIRE_MEMBERSHIP);
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

        $headerEncoded = $this->b64url_encode(wp_json_encode($header));
        $payloadEncoded = $this->b64url_encode(wp_json_encode($payload));

        $signingInput = $headerEncoded . '.' . $payloadEncoded;
        $signature = hash_hmac('sha256', $signingInput, $secret, true);
        $signatureEncoded = $this->b64url_encode($signature);

        return $headerEncoded . '.' . $payloadEncoded . '.' . $signatureEncoded;
    }

    public function memberpress_table_exists()
    {
        global $wpdb;

        $table = $wpdb->prefix . 'mepr_transactions';

        $tableExists = $wpdb->get_var(
            $wpdb->prepare(
                "SHOW TABLES LIKE %s",
                $table
            )
        );

        return ($tableExists === $table);
    }

    public function get_memberpress_membership_info($user_id)
    {
        $info = array(
            'user_id' => intval($user_id),
            'exists'  => false,
            'count'   => 0,
        );

        if (!$user_id)
        {
            return $info;
        }

        if (!$this->memberpress_table_exists())
        {
            return $info;
        }

        global $wpdb;
        $table = $wpdb->prefix . 'mepr_transactions';

        $count = $wpdb->get_var(
            $wpdb->prepare(
                "SELECT COUNT(*) FROM {$table} WHERE user_id = %d",
                $user_id
            )
        );

        $info['count'] = intval($count);
        $info['exists'] = (intval($count) > 0);

        return $info;
    }

    public function get_identity_payload($user)
    {
        $roles = array();

        if (!empty($user->roles) && is_array($user->roles))
        {
            $roles = array_values($user->roles);
        }

        return array(
            'email'      => (string) $user->user_email,
            'first_name' => (string) get_user_meta($user->ID, 'first_name', true),
            'last_name'  => (string) get_user_meta($user->ID, 'last_name', true),
            'roles'      => $roles,
            'membership' => array(
                'memberpress' => $this->get_memberpress_membership_info($user->ID),
            ),
        );
    }

    public function build_payload_for_user($user)
    {
        $issuer = $this->get_issuer();
        $now = time();

        return array(
            'iss'      => $issuer,
            'sub'      => (string) $user->ID,
            'iat'      => $now,
            'nbf'      => $now,
            'exp'      => $now + 3600,
            'user_id'  => (string) $user->ID,
            'identity' => $this->get_identity_payload($user),
        );
    }

    public function build_jwt_for_user($user)
    {
        $secret = $this->get_secret();
        $payload = $this->build_payload_for_user($user);

        return $this->jwt_hs256($payload, $secret);
    }

    public function build_redirect_url($token)
    {
        return add_query_arg(
            array(
                'token' => $token,
            ),
            $this->get_target_url()
        );
    }

    public function button_shortcode()
    {
        if (!is_user_logged_in())
        {
            $login_url = wp_login_url(get_permalink());

            return '<div class="glp-lobos-dev-message"><a class="glp-lobos-dev-button" href="' . esc_url($login_url) . '">Log in to access Lobos Dev</a></div>';
        }

        $buttonText = $this->get_button_text();
        $actionUrl = esc_url(admin_url('admin-post.php'));

        $html  = '<div class="glp-lobos-dev-button-wrap">';
        $html .= '<form method="post" action="' . $actionUrl . '">';
        $html .= '<input type="hidden" name="action" value="' . esc_attr(self::ACTION_LAUNCH) . '">';
        $html .= wp_nonce_field('glp_lobos_dev_launch_action', 'glp_lobos_dev_nonce', true, false);
        $html .= '<button type="submit" class="glp-lobos-dev-button">' . esc_html($buttonText) . '</button>';
        $html .= '</form>';
        $html .= '</div>';

        return $html;
    }

    public function debug_shortcode()
    {
        if (!current_user_can('manage_options'))
        {
            return '<div class="glp-lobos-dev-debug-box"><strong>Lobos Dev Debug:</strong> admin access required.</div>';
        }

        if (!is_user_logged_in())
        {
            return '<div class="glp-lobos-dev-debug-box"><strong>Lobos Dev Debug:</strong> you are not logged in.</div>';
        }

        $user = wp_get_current_user();

        if (!$user || empty($user->ID))
        {
            return '<div class="glp-lobos-dev-debug-box"><strong>Lobos Dev Debug:</strong> unable to identify current user.</div>';
        }

        $secret = $this->get_secret();
        $payload = $this->build_payload_for_user($user);
        $token = '';
        $redirect_url = '';
        $secret_ready = !empty($secret);

        if ($secret_ready)
        {
            $token = $this->build_jwt_for_user($user);
            $redirect_url = $this->build_redirect_url($token);
        }

        $membership_exists = !empty($payload['identity']['membership']['memberpress']['exists']);
        $membership_count = 0;

        if (!empty($payload['identity']['membership']['memberpress']['count']))
        {
            $membership_count = intval($payload['identity']['membership']['memberpress']['count']);
        }

        $html  = '<div class="glp-lobos-dev-debug-box">';
        $html .= '<h3>Lobos Dev Debug</h3>';

        $html .= '<p><strong>User ID:</strong> ' . esc_html($user->ID) . '</p>';
        $html .= '<p><strong>Email:</strong> ' . esc_html($user->user_email) . '</p>';
        $html .= '<p><strong>First Name:</strong> ' . esc_html(get_user_meta($user->ID, 'first_name', true)) . '</p>';
        $html .= '<p><strong>Last Name:</strong> ' . esc_html(get_user_meta($user->ID, 'last_name', true)) . '</p>';
        $html .= '<p><strong>Roles:</strong> ' . esc_html(implode(', ', $user->roles)) . '</p>';
        $html .= '<p><strong>Target URL:</strong> ' . esc_html($this->get_target_url()) . '</p>';
        $html .= '<p><strong>Issuer:</strong> ' . esc_html($this->get_issuer()) . '</p>';
        $html .= '<p><strong>MemberPress Table Exists:</strong> ' . ($this->memberpress_table_exists() ? 'true' : 'false') . '</p>';
        $html .= '<p><strong>MemberPress Membership Exists:</strong> ' . ($membership_exists ? 'true' : 'false') . '</p>';
        $html .= '<p><strong>MemberPress Transaction Count:</strong> ' . esc_html($membership_count) . '</p>';
        $html .= '<p><strong>Require Membership Setting:</strong> ' . esc_html($this->get_require_membership()) . '</p>';

        if (!$membership_exists)
        {
            $html .= '<div class="glp-lobos-dev-debug-warning">Warning: no MemberPress membership transaction found for this user.</div>';
        }

        if (!$secret_ready)
        {
            $html .= '<div class="glp-lobos-dev-debug-warning">Warning: JWT secret is not configured yet.</div>';
        }

        $html .= '<h4>JWT Payload</h4>';
        $html .= '<pre>' . esc_html(wp_json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>';

        $html .= '<h4>JWT Token</h4>';
        if ($secret_ready)
        {
            $html .= '<pre>' . esc_html($token) . '</pre>';
        }
        else
        {
            $html .= '<pre>Secret not configured yet.</pre>';
        }

        $html .= '<h4>Redirect URL Preview</h4>';
        if ($secret_ready)
        {
            $html .= '<pre>' . esc_html($redirect_url) . '</pre>';
        }
        else
        {
            $html .= '<pre>Secret not configured yet.</pre>';
        }

        $html .= '</div>';

        return $html;
    }

    public function handle_launch()
    {
        if (!is_user_logged_in())
        {
            wp_die('You must be logged in to access Lobos Dev.');
        }

        if (!isset($_POST['glp_lobos_dev_nonce']) || !wp_verify_nonce($_POST['glp_lobos_dev_nonce'], 'glp_lobos_dev_launch_action'))
        {
            wp_die('Invalid request.');
        }

        $user = wp_get_current_user();

        if (!$user || empty($user->ID))
        {
            wp_die('Unable to identify current user.');
        }

        $require_membership = $this->get_require_membership();
        $identity = $this->get_identity_payload($user);
        $has_memberpress_membership = !empty($identity['membership']['memberpress']['exists']);
        $secret = $this->get_secret();

        if ($require_membership === '1' && !$has_memberpress_membership)
        {
            wp_die('Active membership required to access Lobos Dev.');
        }

        if (empty($secret))
        {
            wp_die('Lobos Dev plugin secret is not configured yet.');
        }

        $token = $this->build_jwt_for_user($user);
        $redirect_url = $this->build_redirect_url($token);

        wp_redirect($redirect_url);
        exit;
    }

    public function register_settings()
    {
        register_setting(self::SETTINGS_GROUP, self::OPTION_TARGET_URL);
        register_setting(self::SETTINGS_GROUP, self::OPTION_SECRET);
        register_setting(self::SETTINGS_GROUP, self::OPTION_ISSUER);
        register_setting(self::SETTINGS_GROUP, self::OPTION_BUTTON_TEXT);
        register_setting(self::SETTINGS_GROUP, self::OPTION_REQUIRE_MEMBERSHIP);
    }

    public function add_admin_menu()
    {
        add_options_page(
            'Lobos Dev Settings',
            'Lobos Dev',
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
            <h1>Lobos Dev Settings</h1>

            <form method="post" action="options.php">
                <?php settings_fields(self::SETTINGS_GROUP); ?>

                <table class="form-table">
                    <tr>
                        <th scope="row"><label for="glp_lobos_dev_target_url">Target URL</label></th>
                        <td>
                            <input
                                type="text"
                                id="glp_lobos_dev_target_url"
                                name="<?php echo esc_attr(self::OPTION_TARGET_URL); ?>"
                                value="<?php echo esc_attr($this->get_target_url()); ?>"
                                class="regular-text"
                            >
                        </td>
                    </tr>

                    <tr>
                        <th scope="row"><label for="glp_lobos_dev_secret">JWT Secret</label></th>
                        <td>
                            <input
                                type="text"
                                id="glp_lobos_dev_secret"
                                name="<?php echo esc_attr(self::OPTION_SECRET); ?>"
                                value="<?php echo esc_attr($this->get_secret()); ?>"
                                class="regular-text"
                            >
                        </td>
                    </tr>

                    <tr>
                        <th scope="row"><label for="glp_lobos_dev_issuer">JWT Issuer</label></th>
                        <td>
                            <input
                                type="text"
                                id="glp_lobos_dev_issuer"
                                name="<?php echo esc_attr(self::OPTION_ISSUER); ?>"
                                value="<?php echo esc_attr($this->get_issuer()); ?>"
                                class="regular-text"
                            >
                        </td>
                    </tr>

                    <tr>
                        <th scope="row"><label for="glp_lobos_dev_button_text">Button Text</label></th>
                        <td>
                            <input
                                type="text"
                                id="glp_lobos_dev_button_text"
                                name="<?php echo esc_attr(self::OPTION_BUTTON_TEXT); ?>"
                                value="<?php echo esc_attr($this->get_button_text()); ?>"
                                class="regular-text"
                            >
                        </td>
                    </tr>

                    <tr>
                        <th scope="row">Require MemberPress Membership</th>
                        <td>
                            <label>
                                <input
                                    type="checkbox"
                                    name="<?php echo esc_attr(self::OPTION_REQUIRE_MEMBERSHIP); ?>"
                                    value="1"
                                    <?php checked($this->get_require_membership(), '1'); ?>
                                >
                                Require active Lobos membership to launch
                            </label>
                        </td>
                    </tr>
                </table>

                <?php submit_button(); ?>
            </form>

            <hr>

            <h2>Shortcodes</h2>
            <p><code>[<?php echo esc_html(self::SHORTCODE_BUTTON); ?>]</code></p>
            <p><code>[<?php echo esc_html(self::SHORTCODE_DEBUG); ?>]</code></p>
        </div>
        <?php
    }

    public function button_styles()
    {
        echo '
        <style>
            .glp-lobos-dev-button-wrap
            {
                margin: 20px 0;
            }

            .glp-lobos-dev-button
            {
                display: inline-block;
                padding: 12px 20px;
                background: #2271b1;
                color: #ffffff !important;
                text-decoration: none;
                border: 0;
                border-radius: 6px;
                font-weight: 600;
                cursor: pointer;
            }

            .glp-lobos-dev-button:hover
            {
                background: #135e96;
                color: #ffffff !important;
            }

            .glp-lobos-dev-message
            {
                margin: 20px 0;
            }

            .glp-lobos-dev-debug-box
            {
                margin: 20px 0;
                padding: 16px;
                border: 1px solid #ccd0d4;
                background: #ffffff;
                border-radius: 6px;
            }

            .glp-lobos-dev-debug-box pre
            {
                white-space: pre-wrap;
                word-break: break-word;
                background: #f6f7f7;
                padding: 12px;
                border-radius: 4px;
                overflow: auto;
            }

            .glp-lobos-dev-debug-warning
            {
                margin: 12px 0;
                padding: 12px;
                background: #fff8e5;
                border-left: 4px solid #dba617;
            }
        </style>
        ';
    }
}

function glp_lobos_dev_boot_plugin()
{
    static $instance = null;

    if ($instance === null)
    {
        $instance = new GLP_Lobos_Dev_Plugin();
        $instance->init();
    }

    return $instance;
}

glp_lobos_dev_boot_plugin();