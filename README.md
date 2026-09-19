# Geo Buyer Fire Instagram Factory

Облачный автозавод оригинальных Instagram Reels, Stories и каруселей для русскоязычных женщин 35+. Магазин остаётся в bio, закрепах и Highlights; ежедневная лента работает как fashion/lifestyle-медиа и приводит новую аудиторию в профиль.

Контур повторяет рабочую архитектуру Threads‑проекта:

`идеи → редактор и антидубли → compliance → очередь → рендер 9:16/4:5 → официальный Instagram API → аналитика`

## Уже готово

- единая взрослая luxury-палитра и кириллический шрифт `Onest`;
- автоматический рендер коротких двухактных Reels из собственных editorial-кадров;
- автоматический рендер и публикация статичных Stories;
- карусельный формат сохранён для редких полезных серий;
- проверка длины, прав, повторов, рекламных claims и формулировок о репликах;
- клиент официального Instagram Content Publishing API;
- стоп‑кран `AUTOPUBLISH_ENABLED=false`;
- публикация максимум одного поста за запуск;
- публикация работает в GitHub Actions при выключенном компьютере;
- тесты очереди, API-параметров и compliance.

## Локальная проверка

Использовать Python из Workspace Dependencies, где доступен Pillow:

```bash
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -v
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m instagram_factory.cli render
/Users/georgykhitarov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m instagram_factory.cli status
```

## Облачный автопостинг

1. Профессиональный Instagram‑аккаунт Business или Creator.
2. Официальное Meta‑приложение и токен с правом публикации.
3. Instagram User ID.
4. Публичный HTTPS‑адрес для отрендеренных изображений: Meta забирает файлы по URL.
5. GitHub Secrets `INSTAGRAM_ACCESS_TOKEN` и `INSTAGRAM_USER_ID`.

Workflow запускается каждый час, рендерит очередь, публикует публичные медиафайлы в репозиторий и отправляет максимум один запланированный элемент через официальный API.

Через Facebook Login нужны права `pages_show_list`, `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`; для комментариев отдельно `instagram_manage_comments`. Через Instagram Login используются актуальные `instagram_business_*` scope.

Официальная документация Meta: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Важное

Автоматизация работает только через официальный API. Она не использует пароль Instagram, браузерных ботов, скрейпинг, автолайки или массовые DM. Автоматические карусели ограничены десятью карточками. Чужие Reels не скачиваются и не перезаливаются: фабрика использует только собственные или лицензированные исходники.
