FROM python:3.11-slim

WORKDIR /app

# Ya no se instala build-essential: al delegar el producto matricial a la
# calculadora, este servicio dejó de depender de numpy y no compila nada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
