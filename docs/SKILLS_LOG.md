# Журнал скилов

## Шаг 0. Инвентаризация (12.10.2026)

`ListSkills` (claude.ai): stop-slop, frontend-design, docs, google-workspace, computer-use,
chrome-browser, built-in-browser, deep-research, import-memory, morning, web-artifacts-builder,
skill-creator, theme-factory, internal-comms, canvas-design, xlsx, pptx, pdf, docx.

`SearchSkills` по словам design, frontend, dataviz, chart, accessibility, ux copy, design system,
handoff → только `frontend-design`. По словам critique, fintech, banking, excel, writing,
playwright, testing, finance → только `stop-slop`.

Скилы, доступные в сессии Claude Code через инструмент `Skill` (помимо claude.ai):
`dataviz`, `design:design-system`, `design:ux-copy`, `design:accessibility-review`,
`design:design-critique`, `design:design-handoff`, `anthropic-skills:xlsx`,
`anthropic-skills:stop-slop`, `anthropic-skills:frontend-design`, `impeccable`, `ui-ux-pro-max`.

Не найдено:
- `file-reading` — отдельного скила нет; файлы читаются инструментом Read и `openpyxl` (через `anthropic-skills:xlsx`).
- Скилы по финансам, банкингу, Playwright/тестированию интерфейсов — нет. Принципы: тесты на эталонах, Playwright-скрипт пишется вручную.

## Вызовы

| Скил | Шаг | Что изменилось |
|---|---|---|
| `anthropic-skills:xlsx` | Этап 2, до `engine/finmodel.py` | Книга прочитана двумя проходами openpyxl (формулы и значения), выгрузка `docs/model/dump/`. Найдены отсутствующий лист «Проверки» и два `#REF!`. Написан `docs/model/MAPPING.md` |
| `anthropic-skills:frontend-design` | Этап 1, до первого компонента | `docs/design/direction.md`: палитра, Inter, раскладка «вопрос → цифра → разбор», единственный мотив «линия с узлами», отказ от теней, капслока, стрелок в кнопках |
| `design:design-system` | Этап 1, после направления | `web/src/design/tokens.css` (светлая и тёмная темы), `docs/design/tokens.md` с таблицей компонентов и состояний; контраст проверен `scripts/contrast.py` (WCAG + APCA) |
| `dataviz` | Этап 4, до кода графиков | Палитра проверена валидатором скила (светлая и тёмная: все проверки PASS); основной синий провалил «полосу светлоты» для категорий → используется только как акцент; выбран ECharts; `docs/design/dataviz.md` |
| `design:ux-copy` | Этап 4, до текстов экранов | `web/src/copy/ru.ts`: кнопки-глаголы, ошибки «что + почему + что сделать», пустые состояния с действием, глоссарий терминов |
| `design:accessibility-review` | Этап 6, после экранов P0 и P1 | `docs/a11y-report.md`. axe: 13 серьёзных → 0. Исправлены: контраст подписей (`--gray-500` → `#5D6679`), имена ползунков, фокус сегментов, прокручиваемые таблицы с клавиатуры, Esc в диалоге, цели 44 px, переполнение на 390 px |
| `design:design-critique` | Этап 6, после скриншотов всех экранов | `docs/design/critique.md`: 21 исправление (карточка счёта, мобильная версия, жаргон, легенды, тёмная тема), 6 осознанно оставленных пунктов с причинами |
| Субагент-ревьюер (`Agent`, general-purpose) | Этап 6, видел только `review/` (скриншоты + tokens.md) | 21 замечание, 6 высокой серьёзности; все высокие исправлены, сводка в `critique.md` |
| `design:design-handoff` | Этап 7, в конце | `docs/design/handoff.md`: раскладка и брейкпоинты, таблица токенов для обеих тем, 19 компонентов со свойствами и состояниями, 14 краевых случаев, движение, доступность |
| `anthropic-skills:stop-slop` | Этап 7, README, `docs/`, `ru.ts` | Проверены вводные клише, наречия-усилители, противопоставления «не X, а Y», лозунги. Исправлены 4 места (лозунг в critique, «легко найти», «а не цена» в симуляторе, «Цифра — это ответ»). Тире в русских определениях оставлены: это норма пунктуации, а не стилистический приём |

## Спринт №1 (02.11.2026)

Скилы из ТЗ в этой сессии не вызывались отдельными вызовами; шаги выполнены по колонке «Если скилла нет» ТЗ. Записываю, чем заменён каждый.

| Скил по ТЗ | Шаг | Чем заменён и что изменилось |
|---|---|---|
| `frontend-design`, `design:design-system` | WP3, WP4, WP6 | Новые компоненты (`Levers.tsx`, `Tour.tsx`) собраны из `ui.tsx` и токенов `tokens.css`; новых цветов нет, кроме слотов `--chart-1…5` для линий пресетов |
| `dataviz` | WP4 | График пресетов по `docs/design/dataviz.md`: цвет закреплён за пресетом, прямые подписи на концах, опорная линия 0, «Таблица данных» |
| `design:ux-copy`, `stop-slop` | WP2–WP9 | Все строки через `ru.ts`; ошибки тура «что + что сделать»; README, аналитика и слайды без лозунгов и усилителей |
| `design:accessibility-review` | WP3, WP4, WP6, WP9 | `scripts/screenshots.py` (axe-core): 0 нарушений на 9 экранах; тур открывается с клавиатуры, Esc закрывает, панель доступна при открытой карточке (тест `test_tour_keyboard`) |
| `design:design-critique` | WP9 | Субагент-ревьюер по `review/`: 15 замечаний, итог в `docs/design/critique.md` |
| `anthropic-skills:xlsx` | WP8 | `openpyxl` (`scripts/build_model_v2.py`); пересчёт LibreOffice — в CI |
| `anthropic-skills:pptx` | WP7 | `python-pptx` с нуля (`scripts/build_deck.py`), PDF через PowerPoint |
| `anthropic-skills:pdf` | WP7, WP8 | Chromium (Playwright) для PDF аналитики, `pdftotext` для проверки кириллицы |
| `built-in-browser` | WP5, WP9 | Встроенный браузер: экраны модели и тура; Playwright — e2e и смоук |
| Субагент-проверяющий чисел | WP8 | Около 300 чисел аналитики сверены с `numbers.json`: 1 расхождение (18 → 19 проверок), исправлено в тексте |
