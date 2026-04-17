--
-- PostgreSQL database dump
--

\restrict rUoWglh07T9nFduR1bbLNf5xcX8sM2auJkiYhKa1tD2Guc2gnJJLOH1ecQdENzg

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

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
-- Name: admin_role_audit; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.admin_role_audit (
    id integer NOT NULL,
    actor_user_id integer NOT NULL,
    target_user_id integer NOT NULL,
    action character varying(16) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    CONSTRAINT ck_admin_role_audit_action CHECK (((action)::text = ANY ((ARRAY['grant'::character varying, 'revoke'::character varying])::text[])))
);


ALTER TABLE public.admin_role_audit OWNER TO app;

--
-- Name: admin_role_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: app
--

CREATE SEQUENCE public.admin_role_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_role_audit_id_seq OWNER TO app;

--
-- Name: admin_role_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: app
--

ALTER SEQUENCE public.admin_role_audit_id_seq OWNED BY public.admin_role_audit.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO app;

--
-- Name: daily_reports; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.daily_reports (
    id integer NOT NULL,
    date date NOT NULL,
    support_user_id integer NOT NULL,
    status character varying(16) NOT NULL,
    finalized_at timestamp without time zone,
    CONSTRAINT ck_daily_report_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'final'::character varying])::text[])))
);


ALTER TABLE public.daily_reports OWNER TO app;

--
-- Name: daily_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: app
--

CREATE SEQUENCE public.daily_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_reports_id_seq OWNER TO app;

--
-- Name: daily_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: app
--

ALTER SEQUENCE public.daily_reports_id_seq OWNED BY public.daily_reports.id;


--
-- Name: duty_assignments; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.duty_assignments (
    date date NOT NULL,
    slot integer NOT NULL,
    support_user_id integer NOT NULL,
    CONSTRAINT ck_duty_slot_range CHECK (((slot >= 0) AND (slot <= 10)))
);


ALTER TABLE public.duty_assignments OWNER TO app;

--
-- Name: duty_swap_requests; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.duty_swap_requests (
    id integer NOT NULL,
    date date NOT NULL,
    from_slot integer NOT NULL,
    to_slot integer NOT NULL,
    requester_user_id integer NOT NULL,
    target_user_id integer NOT NULL,
    message character varying(500) NOT NULL,
    status character varying(16) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    CONSTRAINT ck_swap_from_slot_range CHECK (((from_slot >= 0) AND (from_slot <= 10))),
    CONSTRAINT ck_swap_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_swap_to_slot_range CHECK (((to_slot >= 0) AND (to_slot <= 10)))
);


ALTER TABLE public.duty_swap_requests OWNER TO app;

--
-- Name: duty_swap_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: app
--

CREATE SEQUENCE public.duty_swap_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.duty_swap_requests_id_seq OWNER TO app;

--
-- Name: duty_swap_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: app
--

ALTER SEQUENCE public.duty_swap_requests_id_seq OWNED BY public.duty_swap_requests.id;


--
-- Name: report_entries; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.report_entries (
    id integer NOT NULL,
    report_id integer NOT NULL,
    minutes integer NOT NULL,
    description character varying(2000) NOT NULL,
    task character varying(500) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.report_entries OWNER TO app;

--
-- Name: report_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: app
--

CREATE SEQUENCE public.report_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.report_entries_id_seq OWNER TO app;

--
-- Name: report_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: app
--

ALTER SEQUENCE public.report_entries_id_seq OWNED BY public.report_entries.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    full_name character varying(200) NOT NULL,
    role character varying(16) NOT NULL,
    password_hash character varying(200) NOT NULL,
    is_active_for_duties boolean NOT NULL
);


ALTER TABLE public.users OWNER TO app;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: app
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO app;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: app
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: admin_role_audit id; Type: DEFAULT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.admin_role_audit ALTER COLUMN id SET DEFAULT nextval('public.admin_role_audit_id_seq'::regclass);


--
-- Name: daily_reports id; Type: DEFAULT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.daily_reports ALTER COLUMN id SET DEFAULT nextval('public.daily_reports_id_seq'::regclass);


--
-- Name: duty_swap_requests id; Type: DEFAULT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_swap_requests ALTER COLUMN id SET DEFAULT nextval('public.duty_swap_requests_id_seq'::regclass);


--
-- Name: report_entries id; Type: DEFAULT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.report_entries ALTER COLUMN id SET DEFAULT nextval('public.report_entries_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: admin_role_audit; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.admin_role_audit (id, actor_user_id, target_user_id, action, created_at) FROM stdin;
9	1	3	grant	2026-04-08 10:37:19.850479
11	1	1	revoke	2026-04-08 10:39:40.787406
12	3	1	grant	2026-04-08 11:00:55.702263
13	3	3	revoke	2026-04-08 11:01:00.376781
17	1	13	grant	2026-04-08 12:22:12.09566
18	1	13	revoke	2026-04-08 12:22:14.14035
19	1	3	grant	2026-04-08 12:22:19.220496
20	3	2	grant	2026-04-08 12:22:57.441421
21	3	2	revoke	2026-04-08 12:29:03.236855
22	3	3	revoke	2026-04-08 12:29:05.092856
23	1	2	grant	2026-04-10 09:20:12.294092
24	1	3	grant	2026-04-10 09:20:14.282265
25	2	3	revoke	2026-04-10 09:21:20.328373
26	2	2	revoke	2026-04-10 09:21:23.671837
27	1	2	grant	2026-04-13 10:22:08.288192
28	1	3	grant	2026-04-13 10:22:09.919773
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.alembic_version (version_num) FROM stdin;
c1d4e8f0a1b2
\.


--
-- Data for Name: daily_reports; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.daily_reports (id, date, support_user_id, status, finalized_at) FROM stdin;
2	2026-04-08	12	draft	\N
3	2026-04-08	13	draft	\N
4	2026-04-08	10	draft	\N
6	2026-04-08	1	draft	\N
8	2026-04-07	2	draft	\N
9	2026-04-09	2	draft	\N
7	2026-04-08	3	final	2026-04-08 12:41:24.62371
5	2026-04-08	4	final	2026-04-08 12:41:47.179796
11	2026-04-08	6	draft	\N
12	2026-04-07	3	draft	\N
13	2026-04-09	3	draft	\N
1	2026-04-08	2	final	2026-04-08 14:50:22.311424
14	2026-04-09	13	draft	\N
15	2026-04-09	12	draft	\N
16	2026-04-09	4	draft	\N
17	2026-04-10	3	draft	\N
18	2026-04-10	12	draft	\N
19	2026-04-10	13	draft	\N
20	2026-04-10	2	draft	\N
21	2026-04-10	4	draft	\N
22	2026-04-10	10	draft	\N
23	2026-04-13	3	draft	\N
24	2026-04-13	9	draft	\N
25	2026-04-13	13	draft	\N
26	2026-04-13	2	draft	\N
27	2026-04-13	10	draft	\N
28	2026-04-13	4	draft	\N
\.


--
-- Data for Name: duty_assignments; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.duty_assignments (date, slot, support_user_id) FROM stdin;
2026-04-08	0	13
2026-04-08	1	13
2026-04-08	2	5
2026-04-08	3	11
2026-04-08	4	3
2026-04-08	5	7
2026-04-08	6	2
2026-04-08	7	10
2026-04-08	8	12
2026-04-08	9	4
2026-04-08	10	6
2026-04-01	0	3
2026-04-01	1	9
2026-04-01	2	4
2026-04-01	3	13
2026-04-01	4	5
2026-04-01	6	2
2026-04-01	7	11
2026-04-01	8	10
2026-04-01	9	6
2026-04-01	10	7
2026-04-09	0	12
2026-04-09	1	12
2026-04-09	2	5
2026-04-09	3	13
2026-04-09	4	6
2026-04-09	5	7
2026-04-09	6	2
2026-04-09	7	11
2026-04-09	8	10
2026-04-09	9	3
2026-04-09	10	4
2026-04-10	0	10
2026-04-10	1	10
2026-04-10	2	5
2026-04-10	3	4
2026-04-10	4	3
2026-04-10	5	7
2026-04-10	6	12
2026-04-10	7	2
2026-04-10	8	13
2026-04-10	9	6
2026-04-10	10	11
2026-04-13	0	9
2026-04-13	1	9
2026-04-13	2	5
2026-04-13	3	13
2026-04-13	4	2
2026-04-13	5	7
2026-04-13	6	12
2026-04-13	7	10
2026-04-13	8	3
2026-04-13	9	6
2026-04-13	10	11
\.


--
-- Data for Name: duty_swap_requests; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.duty_swap_requests (id, date, from_slot, to_slot, requester_user_id, target_user_id, message, status, created_at) FROM stdin;
\.


--
-- Data for Name: report_entries; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.report_entries (id, report_id, minutes, description, task) FROM stdin;
82	7	60	принял 3 обращения	линия 1313-3
83	7	15	переподнял подман контейнеры - опять упало(	техпод сайт
84	7	15	установка MAX на телефон	Кристина Ситнова
85	7	60	установка тонких клиентов 1с	Валерий Пимурзин
86	7	60	получила технику - провёл краткий экскурс - везде авторизовались	Алёна Жемчугова
87	7	10	передал его награду что приезжала	Кирилл Кудисов
88	7	30	не заходило в 1с, оказалось что через SoftEther не хочет, по родной DA зашло, долго не мог понять почему	Регина Сметанкина
89	7	30	печать документов, + связался с бухгалтером - узнать про ЭДО - что бы не печатать через нас	Леонид Сезов
90	7	10	узнал про закупку ноутбуков для Лаксы	Игорь Гришин
91	7	15	помог выяснить за кем moscow.office@sokolov.ru - почтовая группа	Ольга Роденкова
92	7	10	помог выяснить вопрос по корп симке	Максим Синицын
93	7	90	перебирал БУ ноутбуки в поисках живого	Поиск живых ноутбуков
94	7	15	симка по задаче для Натальи Боровик	Екатерина Корегина
95	7	30	установка draw io	Сергей Виноградов
96	7	30	разблокировка УЗ и помог с монтированием папки на маке + поиск и выдача симки корп	Ульяна Трегубова
149	1	180	Работа над v.sokolov.io	v.sokolov.io
150	1	60	Дежурство	Дежурство
151	1	15	Выдача доступа	Выдать доступ к ИР
152	1	15	Установка zoom	Выдать доступ к zoom
153	1	25	Передана логистам	Подготовка ноута к отправке Антипова
154	1	15	Замена мышки	Помощь охране на 3 этаэе
155	1	15	Установка 1с версии 1586	Установка 1c
156	1	25	копирование прав ИР	Установка ИР для Карповой(вызход)
157	1	60	Подготовка ноута	Выход Уварова
158	1	15	Выдана группа	Выдача доступа в ИБЛ
30	5	60	0	Дежурство на линии
31	5	20	Перебирковка	Перебирковка
32	5	20	Пересадка сотрудника	Таргаева Наталья
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.users (id, username, full_name, role, password_hash, is_active_for_duties) FROM stdin;
2	v.ivanov	Иванов Владимир Алексеевич	admin	$2b$12$ZA651O8uaZS07XE0lq3L4.syPsdFfk.QhiHAjofHOMmpaVfbcQJzK	t
3	a.agudalin	Агудалин Александр Ильич	admin	$2b$12$e742NyHIXTY9nLTPx/V5YO3W0SITsTN95K.Hz4/Rsl/.O1vUBjYca	t
4	S.Revin	Ревин Сергей Александрович	support	$2b$12$ZKX6VUih1FXxfFTsC5qdEOU/3O3LghX.ae0TmyBtADa63JL61dkAm	t
5	user	Все	support	$2b$12$bKR8jjiZiBvHCDzQWDAbWu2JNSz3rpXXBt7Cqn9I5nFLdGKvQt98C	t
6	a.lebedev	Лебедев Андрей Евгеньевич	support	$2b$12$.4UTocNzQ0RRJs7DlBhId.wialdz3c7uWTPgRPGXZl2A3m/iEE0e2	t
7	danil.knutov	Кнутов Данил Евгеньевич	support	$2b$12$1I1m6an02wRgwxxLcEbbBuXK.WPp1f1dYArmzA0Gy6elr9i1nHMGe	t
9	a.kashanin	Кашанин Александр Андреевич	support	$2b$12$eAkb58H0.Txixqf0lUttbunSlD75BPVL2UkTcoxV4CsCh9Vybnyu6	t
10	ilya.sadriev	Садриев Илья Павлович	support	$2b$12$WFWyrtxp.ABZZzbcNrLRXuXw.W2.aGRUV3XW2Bi8sDyO9qSchUbci	t
11	evgeniy.kokoulin	Кокоулин Евгений Николаевич	support	$2b$12$XKLEq9dxvH1yrOM1mP3eDu/B10HpunLOx0zgJu5rYmpDFv9jn1O92	t
1	admin	Владимир Дерябов	admin	$2b$12$80uN3ZL.q8x3ljNzTNp/zOojBAZo8me8G/Pk2QwsMHuwz2chsDolW	t
12	evgeniy.chistyakov	Чистяков Евгений Александрович	support	$2b$12$mr6vWhlROnXJjZtfD5J9AOaOO/O54LZ4tHPXuofs8oifsN9Bv9knS	t
13	i.frolov	Фролов Игорь Вадимович	support	$2b$12$1ypMjsaVnskoZHuXrRyzpeEVA4gvFIC8NrwVAMz5oQN4QJ8SnLcse	t
\.


--
-- Name: admin_role_audit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: app
--

SELECT pg_catalog.setval('public.admin_role_audit_id_seq', 28, true);


--
-- Name: daily_reports_id_seq; Type: SEQUENCE SET; Schema: public; Owner: app
--

SELECT pg_catalog.setval('public.daily_reports_id_seq', 28, true);


--
-- Name: duty_swap_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: app
--

SELECT pg_catalog.setval('public.duty_swap_requests_id_seq', 4, true);


--
-- Name: report_entries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: app
--

SELECT pg_catalog.setval('public.report_entries_id_seq', 158, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: app
--

SELECT pg_catalog.setval('public.users_id_seq', 35, true);


--
-- Name: admin_role_audit admin_role_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.admin_role_audit
    ADD CONSTRAINT admin_role_audit_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: daily_reports daily_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.daily_reports
    ADD CONSTRAINT daily_reports_pkey PRIMARY KEY (id);


--
-- Name: duty_assignments duty_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_assignments
    ADD CONSTRAINT duty_assignments_pkey PRIMARY KEY (date, slot);


--
-- Name: duty_swap_requests duty_swap_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_swap_requests
    ADD CONSTRAINT duty_swap_requests_pkey PRIMARY KEY (id);


--
-- Name: report_entries report_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.report_entries
    ADD CONSTRAINT report_entries_pkey PRIMARY KEY (id);


--
-- Name: daily_reports uq_daily_report_date_employee; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.daily_reports
    ADD CONSTRAINT uq_daily_report_date_employee UNIQUE (date, support_user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_admin_role_audit_created_at; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_admin_role_audit_created_at ON public.admin_role_audit USING btree (created_at);


--
-- Name: ix_daily_reports_date; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_daily_reports_date ON public.daily_reports USING btree (date);


--
-- Name: ix_daily_reports_status; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_daily_reports_status ON public.daily_reports USING btree (status);


--
-- Name: ix_daily_reports_support_user_id; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_daily_reports_support_user_id ON public.daily_reports USING btree (support_user_id);


--
-- Name: ix_duty_swap_requests_created_at; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_duty_swap_requests_created_at ON public.duty_swap_requests USING btree (created_at);


--
-- Name: ix_duty_swap_requests_date; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_duty_swap_requests_date ON public.duty_swap_requests USING btree (date);


--
-- Name: ix_duty_swap_requests_requester_user_id; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_duty_swap_requests_requester_user_id ON public.duty_swap_requests USING btree (requester_user_id);


--
-- Name: ix_duty_swap_requests_status; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_duty_swap_requests_status ON public.duty_swap_requests USING btree (status);


--
-- Name: ix_duty_swap_requests_target_user_id; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_duty_swap_requests_target_user_id ON public.duty_swap_requests USING btree (target_user_id);


--
-- Name: ix_report_entries_report_id; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_report_entries_report_id ON public.report_entries USING btree (report_id);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: app
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: app
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: admin_role_audit admin_role_audit_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.admin_role_audit
    ADD CONSTRAINT admin_role_audit_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.users(id);


--
-- Name: admin_role_audit admin_role_audit_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.admin_role_audit
    ADD CONSTRAINT admin_role_audit_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id);


--
-- Name: daily_reports daily_reports_support_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.daily_reports
    ADD CONSTRAINT daily_reports_support_user_id_fkey FOREIGN KEY (support_user_id) REFERENCES public.users(id);


--
-- Name: duty_assignments duty_assignments_support_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_assignments
    ADD CONSTRAINT duty_assignments_support_user_id_fkey FOREIGN KEY (support_user_id) REFERENCES public.users(id);


--
-- Name: duty_swap_requests duty_swap_requests_requester_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_swap_requests
    ADD CONSTRAINT duty_swap_requests_requester_user_id_fkey FOREIGN KEY (requester_user_id) REFERENCES public.users(id);


--
-- Name: duty_swap_requests duty_swap_requests_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.duty_swap_requests
    ADD CONSTRAINT duty_swap_requests_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id);


--
-- Name: report_entries report_entries_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.report_entries
    ADD CONSTRAINT report_entries_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.daily_reports(id);


--
-- PostgreSQL database dump complete
--

\unrestrict rUoWglh07T9nFduR1bbLNf5xcX8sM2auJkiYhKa1tD2Guc2gnJJLOH1ecQdENzg

