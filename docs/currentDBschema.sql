--
-- PostgreSQL database dump
--

\restrict NdKy3Ezi8G4MOCd76YAntF6PtAoKADYGBnNtBAGFqBbN95ekkkQcc8D8uzq2Fzs

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: allergy_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.allergy_options (
    id bigint NOT NULL,
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.allergy_options OWNER TO postgres;

--
-- Name: allergy_options_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.allergy_options_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.allergy_options_id_seq OWNER TO postgres;

--
-- Name: allergy_options_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.allergy_options_id_seq OWNED BY public.allergy_options.id;


--
-- Name: app_options; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.app_options (
    key text NOT NULL,
    json text NOT NULL,
    updated_at bigint NOT NULL
);


ALTER TABLE public.app_options OWNER TO lobos_user;

--
-- Name: external_identities; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.external_identities (
    id bigint NOT NULL,
    lobos_user_id bigint NOT NULL,
    provider text NOT NULL,
    issuer text NOT NULL,
    external_user_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    last_login_at timestamp with time zone
);


ALTER TABLE public.external_identities OWNER TO lobos_user;

--
-- Name: external_identities_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.external_identities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.external_identities_id_seq OWNER TO lobos_user;

--
-- Name: external_identities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.external_identities_id_seq OWNED BY public.external_identities.id;


--
-- Name: lobos_users; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.lobos_users (
    id bigint NOT NULL,
    email text,
    first_name text,
    last_name text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lobos_users OWNER TO lobos_user;

--
-- Name: lobos_users_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.lobos_users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lobos_users_id_seq OWNER TO lobos_user;

--
-- Name: lobos_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.lobos_users_id_seq OWNED BY public.lobos_users.id;


--
-- Name: preference_options; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.preference_options (
    id integer NOT NULL,
    category character varying(64) NOT NULL,
    value character varying(256) NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


ALTER TABLE public.preference_options OWNER TO lobos_user;

--
-- Name: preference_options_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.preference_options_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.preference_options_id_seq OWNER TO lobos_user;

--
-- Name: preference_options_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.preference_options_id_seq OWNED BY public.preference_options.id;


--
-- Name: recipe_generations; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.recipe_generations (
    id integer NOT NULL,
    user_id character varying(128) NOT NULL,
    created_at bigint NOT NULL,
    model character varying(128) NOT NULL,
    prompt_hash character varying(64) NOT NULL,
    prompt text NOT NULL,
    response text NOT NULL
);


ALTER TABLE public.recipe_generations OWNER TO lobos_user;

--
-- Name: recipe_generations_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.recipe_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recipe_generations_id_seq OWNER TO lobos_user;

--
-- Name: recipe_generations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.recipe_generations_id_seq OWNED BY public.recipe_generations.id;


--
-- Name: recipe_results; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.recipe_results (
    id integer NOT NULL,
    user_id character varying(128) NOT NULL,
    created_at bigint NOT NULL,
    request_hash character varying(64) NOT NULL,
    request_json text NOT NULL,
    response_text text NOT NULL,
    model character varying(128),
    prompt_hash character varying(64),
    title character varying(256),
    preview text,
    variant_id bigint,
    recipe_key text,
    title_norm text,
    body_norm text,
    ingredient_signature text,
    distance_score numeric(8,6),
    source_hash text
);


ALTER TABLE public.recipe_results OWNER TO lobos_user;

--
-- Name: recipe_results_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.recipe_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recipe_results_id_seq OWNER TO lobos_user;

--
-- Name: recipe_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.recipe_results_id_seq OWNED BY public.recipe_results.id;


--
-- Name: recipe_variant_queue; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recipe_variant_queue (
    id bigint NOT NULL,
    variant_id bigint NOT NULL,
    job_type text DEFAULT 'backfill_recipes'::text NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    target_recipe_count integer DEFAULT 20 NOT NULL,
    attempt_count integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    locked_by text,
    locked_at timestamp with time zone,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.recipe_variant_queue OWNER TO postgres;

--
-- Name: recipe_variant_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.recipe_variant_queue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recipe_variant_queue_id_seq OWNER TO postgres;

--
-- Name: recipe_variant_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.recipe_variant_queue_id_seq OWNED BY public.recipe_variant_queue.id;


--
-- Name: recipe_variants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recipe_variants (
    id bigint NOT NULL,
    variant_key text NOT NULL,
    variant_version integer DEFAULT 1 NOT NULL,
    name text,
    source_type text DEFAULT 'system'::text NOT NULL,
    preference_json jsonb NOT NULL,
    canonical_json jsonb NOT NULL,
    recipe_count integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_generated_at timestamp with time zone,
    overlay_json jsonb
);


ALTER TABLE public.recipe_variants OWNER TO postgres;

--
-- Name: recipe_variants_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.recipe_variants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recipe_variants_id_seq OWNER TO postgres;

--
-- Name: recipe_variants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.recipe_variants_id_seq OWNED BY public.recipe_variants.id;


--
-- Name: user_allergies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_allergies (
    lobos_user_id bigint NOT NULL,
    allergy_option_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_allergies OWNER TO postgres;

--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.user_preferences (
    lobos_user_id bigint NOT NULL,
    current_weight numeric(6,2),
    goal_weight numeric(6,2),
    height numeric(6,2),
    age integer,
    eating_style text,
    glp1_status text,
    glp1_dosage text,
    onboarding_completed boolean DEFAULT false,
    onboarding_completed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now(),
    meal_type character varying(64),
    macro_preset character varying(128),
    prep character varying(128),
    birth_year smallint,
    current_weight_lb numeric(6,2),
    goal_weight_lb numeric(6,2),
    height_in smallint,
    other_allergy text,
    CONSTRAINT chk_user_preferences_birth_year CHECK (((birth_year IS NULL) OR ((birth_year >= 1900) AND (birth_year <= (EXTRACT(year FROM CURRENT_DATE))::integer)))),
    CONSTRAINT chk_user_preferences_current_weight_lb CHECK (((current_weight_lb IS NULL) OR (current_weight_lb > (0)::numeric))),
    CONSTRAINT chk_user_preferences_goal_weight_lb CHECK (((goal_weight_lb IS NULL) OR (goal_weight_lb > (0)::numeric))),
    CONSTRAINT chk_user_preferences_height_in CHECK (((height_in IS NULL) OR ((height_in >= 24) AND (height_in <= 96))))
);


ALTER TABLE public.user_preferences OWNER TO lobos_user;

--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: lobos_user
--

CREATE TABLE public.user_profiles (
    id integer NOT NULL,
    user_id character varying(128) NOT NULL,
    created_at bigint NOT NULL,
    updated_at bigint NOT NULL,
    eating_style character varying(128) NOT NULL,
    meal_type character varying(64) NOT NULL,
    macro_preset character varying(128) NOT NULL,
    prep character varying(128) NOT NULL,
    email character varying(256),
    first_name character varying(128),
    last_name character varying(128),
    roles text,
    membership text
);


ALTER TABLE public.user_profiles OWNER TO lobos_user;

--
-- Name: user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: lobos_user
--

CREATE SEQUENCE public.user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_profiles_id_seq OWNER TO lobos_user;

--
-- Name: user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: lobos_user
--

ALTER SEQUENCE public.user_profiles_id_seq OWNED BY public.user_profiles.id;


--
-- Name: user_weight_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_weight_log (
    id bigint NOT NULL,
    lobos_user_id bigint NOT NULL,
    weight_lb numeric(6,2) NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    source text DEFAULT 'user'::text NOT NULL,
    CONSTRAINT chk_user_weight_log_weight_lb CHECK ((weight_lb > (0)::numeric))
);


ALTER TABLE public.user_weight_log OWNER TO postgres;

--
-- Name: user_weight_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_weight_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_weight_log_id_seq OWNER TO postgres;

--
-- Name: user_weight_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_weight_log_id_seq OWNED BY public.user_weight_log.id;


--
-- Name: allergy_options id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.allergy_options ALTER COLUMN id SET DEFAULT nextval('public.allergy_options_id_seq'::regclass);


--
-- Name: external_identities id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.external_identities ALTER COLUMN id SET DEFAULT nextval('public.external_identities_id_seq'::regclass);


--
-- Name: lobos_users id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.lobos_users ALTER COLUMN id SET DEFAULT nextval('public.lobos_users_id_seq'::regclass);


--
-- Name: preference_options id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.preference_options ALTER COLUMN id SET DEFAULT nextval('public.preference_options_id_seq'::regclass);


--
-- Name: recipe_generations id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.recipe_generations ALTER COLUMN id SET DEFAULT nextval('public.recipe_generations_id_seq'::regclass);


--
-- Name: recipe_results id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.recipe_results ALTER COLUMN id SET DEFAULT nextval('public.recipe_results_id_seq'::regclass);


--
-- Name: recipe_variant_queue id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variant_queue ALTER COLUMN id SET DEFAULT nextval('public.recipe_variant_queue_id_seq'::regclass);


--
-- Name: recipe_variants id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variants ALTER COLUMN id SET DEFAULT nextval('public.recipe_variants_id_seq'::regclass);


--
-- Name: user_profiles id; Type: DEFAULT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.user_profiles ALTER COLUMN id SET DEFAULT nextval('public.user_profiles_id_seq'::regclass);


--
-- Name: user_weight_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_weight_log ALTER COLUMN id SET DEFAULT nextval('public.user_weight_log_id_seq'::regclass);


--
-- Name: allergy_options allergy_options_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.allergy_options
    ADD CONSTRAINT allergy_options_code_key UNIQUE (code);


--
-- Name: allergy_options allergy_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.allergy_options
    ADD CONSTRAINT allergy_options_pkey PRIMARY KEY (id);


--
-- Name: app_options app_options_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.app_options
    ADD CONSTRAINT app_options_pkey PRIMARY KEY (key);


--
-- Name: external_identities external_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.external_identities
    ADD CONSTRAINT external_identities_pkey PRIMARY KEY (id);


--
-- Name: external_identities external_identities_provider_issuer_external_user_id_key; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.external_identities
    ADD CONSTRAINT external_identities_provider_issuer_external_user_id_key UNIQUE (provider, issuer, external_user_id);


--
-- Name: lobos_users lobos_users_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.lobos_users
    ADD CONSTRAINT lobos_users_pkey PRIMARY KEY (id);


--
-- Name: user_allergies pk_user_allergies; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_allergies
    ADD CONSTRAINT pk_user_allergies PRIMARY KEY (lobos_user_id, allergy_option_id);


--
-- Name: preference_options preference_options_category_value_key; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.preference_options
    ADD CONSTRAINT preference_options_category_value_key UNIQUE (category, value);


--
-- Name: preference_options preference_options_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.preference_options
    ADD CONSTRAINT preference_options_pkey PRIMARY KEY (id);


--
-- Name: recipe_generations recipe_generations_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.recipe_generations
    ADD CONSTRAINT recipe_generations_pkey PRIMARY KEY (id);


--
-- Name: recipe_results recipe_results_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.recipe_results
    ADD CONSTRAINT recipe_results_pkey PRIMARY KEY (id);


--
-- Name: recipe_variant_queue recipe_variant_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variant_queue
    ADD CONSTRAINT recipe_variant_queue_pkey PRIMARY KEY (id);


--
-- Name: recipe_variants recipe_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variants
    ADD CONSTRAINT recipe_variants_pkey PRIMARY KEY (id);


--
-- Name: recipe_variants recipe_variants_variant_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variants
    ADD CONSTRAINT recipe_variants_variant_key_key UNIQUE (variant_key);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (lobos_user_id);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_key UNIQUE (user_id);


--
-- Name: user_weight_log user_weight_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_weight_log
    ADD CONSTRAINT user_weight_log_pkey PRIMARY KEY (id);


--
-- Name: idx_recipe_generations_user_time; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX idx_recipe_generations_user_time ON public.recipe_generations USING btree (user_id, created_at DESC);


--
-- Name: idx_recipe_results_ingredient_signature; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX idx_recipe_results_ingredient_signature ON public.recipe_results USING btree (ingredient_signature);


--
-- Name: idx_recipe_results_source_hash; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX idx_recipe_results_source_hash ON public.recipe_results USING btree (source_hash);


--
-- Name: idx_recipe_results_variant_id; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX idx_recipe_results_variant_id ON public.recipe_results USING btree (variant_id);


--
-- Name: idx_recipe_variant_queue_status_priority; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recipe_variant_queue_status_priority ON public.recipe_variant_queue USING btree (status, priority, available_at, created_at);


--
-- Name: idx_recipe_variant_queue_variant_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recipe_variant_queue_variant_id ON public.recipe_variant_queue USING btree (variant_id);


--
-- Name: idx_recipe_variants_canonical_json_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recipe_variants_canonical_json_gin ON public.recipe_variants USING gin (canonical_json);


--
-- Name: idx_recipe_variants_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recipe_variants_status ON public.recipe_variants USING btree (status);


--
-- Name: idx_recipe_variants_updated_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recipe_variants_updated_at ON public.recipe_variants USING btree (updated_at);


--
-- Name: idx_user_allergies_allergy_option_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_allergies_allergy_option_id ON public.user_allergies USING btree (allergy_option_id);


--
-- Name: idx_user_weight_log_lobos_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_weight_log_lobos_user_id ON public.user_weight_log USING btree (lobos_user_id);


--
-- Name: idx_user_weight_log_recorded_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_weight_log_recorded_at ON public.user_weight_log USING btree (recorded_at);


--
-- Name: idx_user_weight_log_user_recorded_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_weight_log_user_recorded_at ON public.user_weight_log USING btree (lobos_user_id, recorded_at DESC);


--
-- Name: preference_options_cat_active_sort; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX preference_options_cat_active_sort ON public.preference_options USING btree (category, is_active, sort_order);


--
-- Name: recipe_results_user_created; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX recipe_results_user_created ON public.recipe_results USING btree (user_id, created_at DESC);


--
-- Name: recipe_results_user_req_created_idx; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX recipe_results_user_req_created_idx ON public.recipe_results USING btree (user_id, request_hash, created_at DESC);


--
-- Name: recipe_results_user_reqhash_created; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX recipe_results_user_reqhash_created ON public.recipe_results USING btree (user_id, request_hash, created_at DESC);


--
-- Name: recipe_results_user_request_created_idx; Type: INDEX; Schema: public; Owner: lobos_user
--

CREATE INDEX recipe_results_user_request_created_idx ON public.recipe_results USING btree (user_id, request_hash, created_at DESC);


--
-- Name: uq_recipe_variant_queue_active_job; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_recipe_variant_queue_active_job ON public.recipe_variant_queue USING btree (variant_id, job_type) WHERE (status = ANY (ARRAY['queued'::text, 'running'::text]));


--
-- Name: external_identities external_identities_lobos_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.external_identities
    ADD CONSTRAINT external_identities_lobos_user_id_fkey FOREIGN KEY (lobos_user_id) REFERENCES public.lobos_users(id);


--
-- Name: user_allergies fk_user_allergies_allergy_option; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_allergies
    ADD CONSTRAINT fk_user_allergies_allergy_option FOREIGN KEY (allergy_option_id) REFERENCES public.allergy_options(id) ON DELETE CASCADE;


--
-- Name: user_allergies fk_user_allergies_lobos_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_allergies
    ADD CONSTRAINT fk_user_allergies_lobos_user FOREIGN KEY (lobos_user_id) REFERENCES public.lobos_users(id) ON DELETE CASCADE;


--
-- Name: user_weight_log fk_user_weight_log_lobos_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_weight_log
    ADD CONSTRAINT fk_user_weight_log_lobos_user FOREIGN KEY (lobos_user_id) REFERENCES public.lobos_users(id) ON DELETE CASCADE;


--
-- Name: recipe_results recipe_results_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.recipe_results
    ADD CONSTRAINT recipe_results_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.recipe_variants(id);


--
-- Name: recipe_variant_queue recipe_variant_queue_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recipe_variant_queue
    ADD CONSTRAINT recipe_variant_queue_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.recipe_variants(id) ON DELETE CASCADE;


--
-- Name: user_preferences user_preferences_lobos_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: lobos_user
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_lobos_user_id_fkey FOREIGN KEY (lobos_user_id) REFERENCES public.lobos_users(id);


--
-- Name: TABLE allergy_options; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.allergy_options TO lobos_user;


--
-- Name: SEQUENCE allergy_options_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.allergy_options_id_seq TO lobos_user;


--
-- Name: TABLE recipe_variant_queue; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.recipe_variant_queue TO lobos_user;


--
-- Name: SEQUENCE recipe_variant_queue_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.recipe_variant_queue_id_seq TO lobos_user;


--
-- Name: TABLE recipe_variants; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.recipe_variants TO lobos_user;


--
-- Name: SEQUENCE recipe_variants_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.recipe_variants_id_seq TO lobos_user;


--
-- Name: TABLE user_allergies; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.user_allergies TO lobos_user;


--
-- Name: TABLE user_weight_log; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.user_weight_log TO lobos_user;


--
-- Name: SEQUENCE user_weight_log_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.user_weight_log_id_seq TO lobos_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,USAGE ON SEQUENCES TO lobos_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO lobos_user;


--
-- PostgreSQL database dump complete
--

\unrestrict NdKy3Ezi8G4MOCd76YAntF6PtAoKADYGBnNtBAGFqBbN95ekkkQcc8D8uzq2Fzs

