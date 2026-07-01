from __future__ import annotations

RESOURCE_CATEGORY_IDS = frozenset({"communications", "admin", "monitoring", "services"})

DEFAULT_USEFUL_RESOURCES: list[dict] = [
    {
        "slug": "open-webui",
        "title": "Open WebUI",
        "description": "Интерфейс LLM для работы команды",
        "url": "https://i.hpdd.ru/",
        "image_path": "./resource-images/open-webui.png",
        "color": "#0f172a",
        "categories": ["admin"],
        "sort_order": 10,
    },
    {
        "slug": "outlook-admin",
        "title": "Админка Outlook",
        "description": "Администрирование почты Outlook",
        "url": (
            "https://mail.hpdd.ru/owa/auth/logon.aspx?replaceCurrent=1&reason=3&url=https%3a%2f%2fmail.hpdd.ru%2fowa%2fauth%2flogon.aspx%3furl%3dhttps%253a%252f%252fmail.hpdd.ru%252fecp%252f%253fexsvurl%253d1%2526p%253dDistributionGroups%23replaceCurrent%3d1"
        ),
        "image_path": "./resource-images/outlook-admin.png",
        "color": "#0078d4",
        "categories": ["communications"],
        "sort_order": 20,
    },
    {
        "slug": "youtrack",
        "title": "YouTrack",
        "description": "Трекер задач команды",
        "url": (
            "https://youtrack.hpdd.ru/hub/auth/login?response_type=token&client_id=386f73f9-b1a1-4a9a-8fa6-e9184a1471d0&redirect_uri=https:%2F%2Fyoutrack.hpdd.ru%2Foauth&scope=386f73f9-b1a1-4a9a-8fa6-e9184a1471d0%20Upsource%20TeamCity%20YouTrack%2520Slack%2520Integration%200-0-0-0-0&state=f59cee64-165b-4121-b407-b5b7889da362"
        ),
        "image_path": "./resource-images/youtrack.png",
        "color": "#e91e63",
        "categories": ["services"],
        "sort_order": 30,
    },
    {
        "slug": "gitlab",
        "title": "GitLab",
        "description": "Репозитории, merge requests и CI/CD",
        "url": "https://git.sokolov.io/",
        "image_path": "./resource-images/gitlab.png",
        "color": "#fc6d26",
        "categories": ["services"],
        "sort_order": 35,
    },
    {
        "slug": "graylog",
        "title": "Graylog",
        "description": "Мониторинг и логи",
        "url": "https://new-graylog.corp.hpdd.ru/welcome",
        "image_path": "./resource-images/graylog.png",
        "color": "#0ea5e9",
        "categories": ["monitoring"],
        "sort_order": 40,
    },
    {
        "slug": "cyber-backup",
        "title": "КиберБэкап",
        "description": "Портал резервного копирования",
        "url": "https://hpdd-bcp-mng02.corp.hpdd.ru:9877/",
        "image_path": "./resource-images/cyber-backup.png",
        "color": "#1d4ed8",
        "categories": ["services"],
        "sort_order": 50,
    },
    {
        "slug": "bitrix-admin",
        "title": "Админка Битрикс",
        "description": "Администрирование портала Битрикс",
        "url": "https://portal.hpdd.ru/bitrix/admin/user_edit.php?lang=ru&ID=3582&user_edit_active_tab=edit1#authorize",
        "image_path": "./resource-images/bitrix-admin.png",
        "color": "#38bdf8",
        "categories": ["communications"],
        "sort_order": 60,
    },
    {
        "slug": "hrlink",
        "title": "HRlink",
        "description": "Личный кабинет сотрудника",
        "url": "https://lk.hr-link.ru/employee",
        "image_path": "./resource-images/hrlink.png",
        "color": "#2563eb",
        "categories": ["services"],
        "sort_order": 70,
    },
    {
        "slug": "zoom-admin",
        "title": "Админка Zoom",
        "description": "Панель управления Zoom",
        "url": "https://hpdd-ru.zoom.us/myhome",
        "image_path": "./resource-images/zoom-admin.png",
        "color": "#2563eb",
        "categories": ["communications"],
        "sort_order": 80,
    },
    {
        "slug": "servicedesk",
        "title": "ServiceDesk",
        "description": "Система заявок и обращений",
        "url": "https://esd.hpdd.ru/HomePage.do?view_type=my_view",
        "image_path": "./resource-images/servicedesk.png",
        "color": "#0f172a",
        "categories": ["services"],
        "sort_order": 90,
    },
    {
        "slug": "proxy-admin",
        "title": "Proxy admin",
        "description": "Панель администрирования Proxy",
        "url": "https://proxy-portal.hpdd.ru/",
        "image_path": "./resource-images/proxy-admin.png",
        "color": "#1f2937",
        "categories": ["admin"],
        "sort_order": 100,
    },
    {
        "slug": "softbalance-canteen-licenses",
        "title": "Менеджер лицензий для Столовых",
        "description": "СофтБаланс — управление лицензиями столовых",
        "url": "http://10.0.15.18:5171/index",
        "image_path": "./resource-images/softbalance-license-manager.png",
        "color": "#1e40af",
        "categories": ["services"],
        "sort_order": 110,
    },
    {
        "slug": "dokuwiki-it-kb",
        "title": "База знаний IT (DokuWiki)",
        "description": "Realize — база знаний техподдержки",
        "url": (
            "http://dokuwiki.corp.hpdd.ru/doku.php/"
            "%D1%82%D0%B5%D1%85%D0%BF%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%BA%D0%B0/exchange/start?do=login"
        ),
        "image_path": "./resource-images/dokuwiki-kb.png",
        "color": "#2563eb",
        "categories": ["services"],
        "sort_order": 115,
    },
    {
        "slug": "mobicontrol",
        "title": "MobiControl",
        "description": "SOTI MobiControl — управление Apple Mac",
        "url": (
            "https://mdm.corp.hpdd.ru/MobiControl/WebConsole/home/dashboard/devices"
            "?subGroups=false"
        ),
        "image_path": "./resource-images/mobicontrol.png",
        "color": "#374151",
        "categories": ["admin"],
        "sort_order": 120,
    },
]


def normalize_resource_categories(categories: list[str] | None) -> list[str]:
    if not categories:
        raise ValueError("Нужна хотя бы одна категория фильтра")
    out: list[str] = []
    seen: set[str] = set()
    for raw in categories:
        cid = str(raw or "").strip()
        if cid not in RESOURCE_CATEGORY_IDS:
            raise ValueError(f"Неизвестная категория: {cid}")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    if not out:
        raise ValueError("Нужна хотя бы одна категория фильтра")
    return out
