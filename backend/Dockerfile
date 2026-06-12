FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy the full source first so the editable install can discover the `app`
# package deterministically (psycopg[binary] and bcrypt<4.1 ship manylinux
# wheels, so no build toolchain is required on the slim image).
COPY . /app
RUN pip install --no-cache-dir -e .

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
