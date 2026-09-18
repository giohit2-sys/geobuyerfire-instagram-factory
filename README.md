# Geo Buyer Fire Instagram Factory

Автозавод оригинальных развлекательных Instagram‑каруселей для женщин 35+. Магазин остаётся в bio, закрепах и Highlights; ежедневная лента работает как медиа и приводит новую аудиторию в профиль.

Контур повторяет рабочую архитектуру Threads‑проекта:

`идеи → редактор и антидубли → compliance → очередь → детерминированный рендер 1080×1350 → официальный Instagram API → аналитика`

## Уже готово

- один неизменный фирменный фон и один кириллический шрифт `Onest` для всех карточек;
- очередь из четырёх оригинальных каруселей по 20 карточек — по одной в день;
- проверка длины, прав, повторов, рекламных claims и формулировок о репликах;
- клиент официального Instagram Content Publishing API;
- стоп‑кран `AUTOPUBLISH_ENABLED=false`;
- публикация максимум одного поста за запуск;
- тесты рендера, очереди и compliance.

## Локальная проверка

Использовать Python из Workspace Dependencies, где доступен Pillow:

```bash
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -v
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m instagram_factory.cli render
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m instagram_factory.cli status
```

## Что нужно для реального автопостинга

1. Профессиональный Instagram‑аккаунт Business или Creator.
2. Официальное Meta‑приложение и токен с правом публикации.
3. Instagram User ID.
4. Публичный HTTPS‑адрес для отрендеренных изображений: Meta забирает файлы по URL.
5. Заполненный `.env` на основе `.env.example`.
6. После тестовой публикации включить `AUTOPUBLISH_ENABLED=true`.

Через Facebook Login нужны права `pages_show_list`, `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`; для комментариев отдельно `instagram_manage_comments`. Через Instagram Login используются актуальные `instagram_business_*` scope.

Официальная документация Meta: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Важное

Автоматизация работает только через официальный API. Она не использует пароль Instagram, браузерных ботов, скрейпинг, автолайки или массовые DM. Нативный Instagram поддерживает 20 карточек, а официальный Content Publishing API — пока 10. Поэтому 20-карточные флагманские посты публикуются нативно; полностью автоматический API-режим использует две связанные части по 10.
