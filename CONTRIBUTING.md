# Руководство для контрибьюторов

Спасибо за интерес к Deep Dublicator!

## 🌿 Ветвление

- `main` — стабильная ветка (только теги релизов).
- `develop` — основная ветка для разработки.
- `feature/название-фичи` — новые фичи (ответвляются от `develop`).
- `fix/название-бага` — исправления (ответвляются от `develop`).

Pull Request делаются в ветку `develop`.

## 📝 Коммиты

Мы используем [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: ...` — новая фича.
- `fix: ...` — исправление бага.
- `docs: ...` — документация.
- `refactor: ...` — рефакторинг без изменения логики.
- `test: ...` — добавление или правка тестов.
- `ci: ...` — изменения в CI/CD.
- `chore: ...` — рутина (обновление зависимостей, версии).

## ✅ Definition of Done (DoD)

Задача считается выполненной, если:
1. Код проходит линтер (`ruff check`).
2. Все тесты зеленые (`pytest tests/ -q`), покрытие не упало.
3. Для новых фич добавлены/обновлены тесты.
4. Обновлен `CHANGELOG.md`.
5. CI на GitHub Actions прошел успешно на всех 3 ОС (Windows, Linux, macOS).

## 🚀 Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows
pip install -r requirements-dev.txt
pytest tests/ -q```


