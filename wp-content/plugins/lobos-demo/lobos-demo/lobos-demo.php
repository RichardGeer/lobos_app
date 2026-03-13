<?php
/**
 * Plugin Name: Lobos Demo SSO
 * Description: Lobos Demo SSO plugin with button shortcode, debug shortcode, JWT redirect, MemberPress membership detection, and admin settings.
 * Version: 0.7
 * Author: Paul
 */

if (!defined('ABSPATH'))
{
    exit;
}

if (!class_exists('Lobos_Demo_SSOPlugin'))
{
    class Lobos_Demo_SSO_Plugin
    {
        const OPTION_KEY = 'lobos_dev_sso_options';

        const DEFAULT_URL = 'http://my.lobos.com:8000/login';
        const DEFAULT_SECRET = '5FqrSBGbnTwx1uJe05H65312mpuLNP8swfmQCdwCoOETIMy7KR5lMUS4ipXfZ5fT';
        const DEFAULT_ISSUER = 'wp-sim';
        const DEFAULT_REQUIRE_MEMBERSHIP = 0;

        public function __construct()
        {
            add_action('admin_menu', array($this, 'admin_menu'));
            add_action('admin_init', array($this, 'admin_init'));

            add_shortcode('lobos_demo_button', array($this, 'shortcode_button'));
            add_shortcode('lobos_demo_debug', array($this, 'shortcode_debug'));
    
            add_action('init', array($this, 'maybe_handle_actions'));
        }

        public function admin_menu()
        {
            add_options_page(
                'Lobos Dev SSO',
                'Lobos Dev SSO',
                'manage_options',
                'lobos-dev-sso',
                array($this, 'settings_page')
            );
        }

        public function admin_init()
        {
            register_setting(
                'lobos_dev_sso_group',
                self::OPTION_KEY,
                array($this, 'sanitize_options')
            );
        }

        public function sanitize_options($input)
        {
            $existing = $this->get_options();

            $output = array();
            $output['target_url'] = isset($input['target_url']) ? esc_url_raw(trim($input['target_url'])) : $existing['target_url'];
            $output['secret'] = isset($input['secret']) ? trim($input['secret']) : $existing['secret'];
            $output['issuer'] = isset($input['issuer']) ? sanitize_text_field(trim($input['issuer'])) : $existing['issuer'];
            $output['require_membership'] = !empty($input['require_membership']) ? 1 : 0;

            return $output;
        }

        public function get_options()
        {
            $defaults = array(
                'target_url' => self::DEFAULT_URL,
                'secret' => self::DEFAULT_SECRET,
                'issuer' => self::DEFAULT_ISSUER,
                'require_membership' => self::DEFAULT_REQUIRE_MEMBERSHIP,
            );

            $saved = get_option(self::OPTION_KEY, array());

            if (!is_array($saved))
            {
                $saved = array();
            }

            return wp_parse_args($saved, $defaults);
        }

        public function settings_page()
        {
            if (!current_user_can('manage_options'))
            {
                return;
            }

            $options = $this->get_options();
            ?>
            <div class="wrap">
                <h1>Lobos Dev SSO Settings</h1>

                <form method="post" action="options.php">
                    <?php settings_fields('lobos_dev_sso_group'); ?>

                    <table class="form-table" role="presentation">
                        <tr>
                            <th scope="row"><label for="lobos_dev_target_url">Target URL</label></th>
                            <td>
                                <input
                                    type="url"
                                    id="lobos_dev_target_url"
                                    name="<?php echo esc_attr(self::OPTION_KEY); ?>[target_url]"
                                    value="<?php echo esc_attr($options['target_url']); ?>"
                                    class="regular-text"
                                />
                            </td>
                        </tr>

                        <tr>
                            <th scope="row"><label for="lobos_dev_secret">JWT Secret</label></th>
                            <td>
                                <input
                                    type="text"
                                    id="lobos_dev_secret"
                                    name="<?php echo esc_attr(self::OPTION_KEY); ?>[secret]"
                                    value="<?php echo esc_attr($options['secret']); ?>"
                                    class="regular-text"
                                />
                            </td>
                        </tr>

                        <tr>
                            <th scope="row"><label for="lobos_dev_issuer">Issuer</label></th>
                            <td>
                                <input
                                    type="text"
                                    id="lobos_dev_issuer"
                                    name="<?php echo esc_attr(self::OPTION_KEY); ?>[issuer]"
                                    value="<?php echo esc_attr($options['issuer']); ?>"
                                    class="regular-text"
                                />
                            </td>
                        </tr>

                        <tr>
                            <th scope="row">Require Membership</th>
                            <td>
                                <label>
                                    <input
                                        type="checkbox"
                                        name="<?php echo esc_attr(self::OPTION_KEY); ?>[require_membership]"
                                        value="1"
                                        <?php checked(!empty($options['require_membership'])); ?>
                                    />
                                    Require an active MemberPress membership before redirect
                                </label>
                            </td>
                        </tr>
                    </table>

                    <?php submit_button(); ?>
                </form>
            </div>
            <?php
        }

        public function shortcode_button($atts = array())
        {
            if (!is_user_logged_in())
            {
                return '<p>You must be logged in to access Lobos Dev.</p>';
            }

            $action_url = add_query_arg(array('lobos_dev_action' => 'go'), home_url('/'));

            ob_start();
            ?>
            <form method="post" action="<?php echo esc_url($action_url); ?>">
                <?php wp_nonce_field('lobos_dev_go', 'lobos_dev_nonce'); ?>
                <button type="submit">Open Lobos Dev</button>
            </form>
            <?php
            return ob_get_clean();
        }

        public function shortcode_debug($atts = array())
        {
            if (!is_user_logged_in())
            {
                return '<p>You must be logged in to view Lobos Dev Debug.</p>';
            }

            if (!current_user_can('manage_options'))
            {
                return '<p>Lobos Dev Debug is currently admin only.</p>';
            }

            $action_url = add_query_arg(array('lobos_dev_action' => 'debug'), home_url('/'));

            ob_start();
            ?>
            <form method="post" action="<?php echo esc_url($action_url); ?>">
                <?php wp_nonce_field('lobos_dev_debug', 'lobos_dev_nonce'); ?>
                <button type="submit">Lobos Dev Debug</button>
            </form>
            <?php
            return ob_get_clean();
        }

        public function maybe_handle_actions()
        {
            if (empty($_GET['lobos_dev_action']))
            {
                return;
            }

            $action = sanitize_text_field(wp_unslash($_GET['lobos_dev_action']));

            if ($action !== 'go' && $action !== 'debug')
            {
                return;
            }

            if ($_SERVER['REQUEST_METHOD'] !== 'POST')
            {
                return;
            }

            if (!is_user_logged_in())
            {
                wp_die('You must be logged in.');
            }

            if (empty($_POST['lobos_dev_nonce']))
            {
                wp_die('Missing nonce.');
            }

            $nonce = sanitize_text_field(wp_unslash($_POST['lobos_dev_nonce']));

            if ($action === 'go' && !wp_verify_nonce($nonce, 'lobos_dev_go'))
            {
                wp_die('Invalid nonce.');
            }

            if ($action === 'debug' && !wp_verify_nonce($nonce, 'lobos_dev_debug'))
            {
                wp_die('Invalid nonce.');
            }

            if ($action === 'debug')
            {
                if (!current_user_can('manage_options'))
                {
                    wp_die('Admin access required for debug.');
                }

                $this->render_debug_page();
                exit;
            }

            $this->handle_redirect();
            exit;
        }

        private function handle_redirect()
        {
            $options = $this->get_options();
            $target_url = trim($options['target_url']);
            $secret = trim($options['secret']);
            $require_membership = !empty($options['require_membership']);

            if (empty($target_url))
            {
                wp_die('Lobos Dev target URL is not configured.');
            }

            if (empty($secret) || $secret === 'REPLACE_ME')
            {
                wp_die('Lobos Dev plugin secret is not configured yet.');
            }

            $user = wp_get_current_user();
            $membership_info = $this->get_memberpress_membership_info($user->ID);

            if ($require_membership && empty($membership_info['exists']))
            {
                wp_die('Active membership required to access Lobos Dev.');
            }

            $payload = $this->build_jwt_payload($user, $membership_info, $options);
            $jwt = $this->jwt_encode_hs256($payload, $secret);

            $redirect_url = add_query_arg(array('token' => rawurlencode($jwt)), $target_url);
            wp_redirect($redirect_url);
            exit;
        }

        private function render_debug_page()
        {
            $options = $this->get_options();
            $user = wp_get_current_user();
            $membership_info = $this->get_memberpress_membership_info($user->ID);
            $payload = $this->build_jwt_payload($user, $membership_info, $options);
            $jwt = $this->jwt_encode_hs256($payload, $options['secret']);
            $redirect_url = add_query_arg(array('token' => rawurlencode($jwt)), $options['target_url']);

            nocache_headers();
            ?>
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Lobos Dev Debug</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 30px; line-height: 1.5; }
                    pre { background: #f4f4f4; padding: 12px; overflow: auto; }
                    h1, h2 { margin-top: 24px; }
                    .warn { color: #b35b00; font-weight: bold; }
                </style>
            </head>
            <body>
                <h1>Lobos Dev Debug</h1>

                <p><strong>User ID:</strong> <?php echo esc_html($user->ID); ?></p>
                <p><strong>Email:</strong> <?php echo esc_html($user->user_email); ?></p>
                <p><strong>First Name:</strong> <?php echo esc_html($user->first_name); ?></p>
                <p><strong>Last Name:</strong> <?php echo esc_html($user->last_name); ?></p>
                <p><strong>Roles:</strong> <?php echo esc_html(implode(', ', (array) $user->roles)); ?></p>

                <p><strong>Target URL:</strong> <?php echo esc_html($options['target_url']); ?></p>
                <p><strong>Issuer:</strong> <?php echo esc_html($options['issuer']); ?></p>

                <p><strong>MemberPress Table Exists:</strong> <?php echo $membership_info['table_exists'] ? 'true' : 'false'; ?></p>
                <p><strong>MemberPress Membership Exists:</strong> <?php echo $membership_info['exists'] ? 'true' : 'false'; ?></p>
                <p><strong>MemberPress Transaction Count:</strong> <?php echo esc_html((string) $membership_info['count']); ?></p>
                <p><strong>Require Membership Setting:</strong> <?php echo !empty($options['require_membership']) ? '1' : '0'; ?></p>

                <?php if (!$membership_info['exists']) : ?>
                    <p class="warn">Warning: no MemberPress membership transaction found for this user.</p>
                <?php endif; ?>

                <h2>MemberPress Memberships</h2>
                <pre><?php echo esc_html(wp_json_encode($membership_info['memberships'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>

                <h2>JWT Payload</h2>
                <pre><?php echo esc_html(wp_json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>

                <h2>JWT Token</h2>
                <pre><?php echo esc_html($jwt); ?></pre>

                <h2>Redirect URL Preview</h2>
                <pre><?php echo esc_html($redirect_url); ?></pre>
            </body>
            </html>
            <?php
        }

        private function build_jwt_payload($user, $membership_info, $options)
        {
            $now = time();

            return array(
                'iss' => (string) $options['issuer'],
                'sub' => (string) $user->ID,
                'iat' => $now,
                'nbf' => $now,
                'exp' => $now + 3600,
                'user_id' => (string) $user->ID,
                'identity' => array(
                    'email' => (string) $user->user_email,
                    'first_name' => (string) $user->first_name,
                    'last_name' => (string) $user->last_name,
                    'roles' => array_values((array) $user->roles),
                    'membership' => array(
                        'memberpress' => array(
                            'user_id' => (int) $user->ID,
                            'exists' => !empty($membership_info['exists']),
                            'count' => (int) $membership_info['count'],
                            'memberships' => array_values($membership_info['memberships']),
                        ),
                    ),
                ),
            );
        }

        private function get_memberpress_membership_info($user_id)
        {
            global $wpdb;

            $result = array(
                'table_exists' => false,
                'exists' => false,
                'count' => 0,
                'memberships' => array(),
            );

            $transactions_table = $wpdb->prefix . 'mepr_transactions';
            $posts_table = $wpdb->posts;

            $table_found = $wpdb->get_var(
                $wpdb->prepare('SHOW TABLES LIKE %s', $transactions_table)
            );

            if ($table_found !== $transactions_table)
            {
                return $result;
            }

            $result['table_exists'] = true;

            $rows = $wpdb->get_results(
                $wpdb->prepare(
                    "
                    SELECT
                        t.id AS transaction_id,
                        t.user_id,
                        t.product_id AS membership_id,
                        t.status,
                        p.post_title AS membership_title
                    FROM {$transactions_table} t
                    LEFT JOIN {$posts_table} p
                        ON p.ID = t.product_id
                    WHERE t.user_id = %d
                      AND t.status IN ('complete', 'confirmed')
                    ORDER BY t.id DESC
                    ",
                    $user_id
                ),
                ARRAY_A
            );

            if (empty($rows))
            {
                return $result;
            }

            $memberships_by_id = array();

            foreach ($rows as $row)
            {
                $membership_id = isset($row['membership_id']) ? (int) $row['membership_id'] : 0;

                if ($membership_id <= 0)
                {
                    continue;
                }

                if (!isset($memberships_by_id[$membership_id]))
                {
                    $memberships_by_id[$membership_id] = array(
                        'id' => $membership_id,
                        'title' => isset($row['membership_title']) ? (string) $row['membership_title'] : '',
                        'status' => isset($row['status']) ? (string) $row['status'] : '',
                    );
                }
            }

            $result['memberships'] = array_values($memberships_by_id);
            $result['count'] = count($result['memberships']);
            $result['exists'] = ($result['count'] > 0);

            return $result;
        }

        private function base64url_encode($data)
        {
            return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
        }

        private function jwt_encode_hs256($payload, $secret)
        {
            $header = array(
                'alg' => 'HS256',
                'typ' => 'JWT',
            );

            $segments = array();
            $segments[] = $this->base64url_encode(wp_json_encode($header));
            $segments[] = $this->base64url_encode(wp_json_encode($payload));

            $signing_input = implode('.', $segments);
            $signature = hash_hmac('sha256', $signing_input, $secret, true);
            $segments[] = $this->base64url_encode($signature);

            return implode('.', $segments);
        }
    }

    new Lobos_Demo_SSO_Plugin();
}