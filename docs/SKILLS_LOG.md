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
