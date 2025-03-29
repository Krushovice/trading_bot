# Используем официальный образ Python 3.11 в режиме slim
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /bot

# Устанавливаем системные зависимости (если нужно, можно расширить список)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry (чтобы собирать зависимости, устанавливать их во внутренний venv)
RUN pip install --upgrade pip \
    && pip install poetry

# Копируем только pyproject.toml и poetry.lock (если есть), чтобы poetry install срабатывал корректно по кэшу
COPY pyproject.toml poetry.lock* /bot/

# Устанавливаем зависимости.
# --no-root – если не нужно устанавливать сам пакет как библиотеку,
# --no-dev – если в контейнере не нужны dev-зависимости. Настраивается по необходимости.
RUN poetry config virtualenvs.create true
RUN poetry install --no-interaction --no-ansi --no-root

# Теперь копируем остальной код
COPY . /bot

# При желании можно выставить ENV, чтобы poetry знала, где искать venv
# ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Запускаем бота через poetry (используя виртуальное окружение)
CMD ["poetry", "run", "python", "main.py"]
