## Перенос логики из Project12

- **Файлы:** `service.py`, `handlers.py`, `sql.txt` и `database.py`.
- **Новые функции:**
  - `build_quiz_keyboard`, `format_results`, `new_quiz`, `start_quiz_session`, `set_question_index`, `record_answer`, `get_quiz_state`, `finish_quiz_session` – обрабатывают сценарий квиза и состояние в YDB.
- **Перенесённая логика:**
  - Сценарии команд `/start`, `/quiz`, остановки игры и обработка inline-ответов (из `app/handlers/*.py` Project12).
  - Структура вопросов и проверка ответов (из `app/logic.py`).
  - Учёт статистики пользователя (из `app/db/quiz.py`).
- **Изменения в схеме данных:** таблица `quiz_state` расширена полями `username`, `correct_answers`, `incorrect_answers`, `is_active` для хранения состояний/статистики.
- **Упрощения/TODO:** отсутствуют – поведение соответствует Project12, но теперь хранится в YDB через существующий слой `database.py`.
