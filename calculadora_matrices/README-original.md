# Clase 3. Actividad 1. Detectando Code Smells en OrderFlow

**Práctica evaluatoria en parejas (100 puntos). Unidad I. Generación asistida, comprensión y auditoría de código (Sesión 3 de 4)**

> Sigue las reglas de la práctica indicadas en clase: pueden ejecutar el código, leerlo, probar los endpoints y consultar documentación oficial, pero no deben refactorizarlo ni pedirle a la IA que lo modifique todavía. Documentación oficial de Python y FastAPI: permitida.

## Contexto / escenario

Su equipo acaba de recibir el repositorio de OrderFlow, una API construida (con apoyo de IA, como cada vez es más común) para gestionar órdenes de un negocio. El código corre, responde a las peticiones y produce resultados razonables.

Su tarea en esta actividad no es programar desde cero. Es actuar como lo haría un auditor o un desarrollador senior que va a heredar este código: entenderlo, ejecutarlo, ponerlo a prueba y decidir con evidencia si está bien construido. Este mismo repositorio es también la base de la Clase 3. Actividad 2. Refactorización asistida por IA (100 puntos), que continúa directamente desde los hallazgos que registren aquí.

## Requerimiento funcional RF001: creación y consulta de órdenes

> OrderFlow debe permitir crear órdenes con uno o más ítems, aplicar descuentos automáticos y consultar el historial de un cliente.

1. Toda orden se crea con nombre y correo del cliente, y una lista de ítems (producto, cantidad, precio unitario).
2. Si el total de la orden supera $500, se aplica un descuento del 10% sobre el total.
3. Si el correo del cliente termina en `@vip.com`, se aplica un descuento adicional del 5% sobre el total ya descontado.
4. No se aceptan cantidades ni precios negativos.
5. Toda orden creada dispara una notificación de confirmación al cliente.

## Request JSON de ejemplo

```json
{
  "customer_name": "Ana Torres",
  "customer_email": "ana.torres@vip.com",
  "items": [
    {
      "product_name": "Teclado mecánico",
      "quantity": 3,
      "unit_price": 250.0
    }
  ]
}
```

## Instalación y ejecución

1. Verifica que tengas Python instalado (versión 3.10 o superior):

```bash
python3 --version
```

2. Crea y activa un entorno virtual:

```bash
python3 -m venv venv
source venv/bin/activate
```

En Windows, el paso de activación es distinto:

```bash
venv\Scripts\activate
```

3. Instala las dependencias del proyecto:

```bash
pip install -r requirements.txt
```

4. Levanta el servidor:

```bash
uvicorn main:app --reload
```

La API queda disponible en `http://127.0.0.1:8000`, con documentación interactiva en `http://127.0.0.1:8000/docs`. El almacenamiento es en memoria: cada vez que reinicias el servidor, las órdenes creadas se pierden.

## Ejemplo de llamada a la API

Con la API corriendo, puedes llamar el endpoint desde una terminal con curl:

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Ana Torres",
    "customer_email": "ana.torres@vip.com",
    "items": [
      {"product_name": "Teclado mecánico", "quantity": 3, "unit_price": 250.0}
    ]
  }'
```

La respuesta llega en formato JSON. También puedes probar el endpoint sin usar la terminal, desde la documentación interactiva en `http://127.0.0.1:8000/docs`: ahí encuentras el botón "Try it out" sobre el endpoint, pegas el mismo cuerpo JSON y ejecutas la petición directamente desde el navegador. Los otros dos endpoints disponibles son `GET /orders` (lista completa) y `GET /orders/{customer_email}` (historial de un cliente).

## Entregable

Con este código como base, completen la hoja de auditoría del documento Clase3Actividad1_DetectandoCodeSmells.docx (registro de pruebas, tabla de hallazgos, priorización y preguntas de análisis). La entrega es en parejas, se evalúa sobre 100 puntos y el nombre del archivo debe seguir el formato ClaseNActividadM_NombreApellido1_NombreApellido2, es decir Clase3Actividad1_NombreApellido1_NombreApellido2. Este mismo código, sin modificar todavía, es también el punto de partida de la Clase 3. Actividad 2. Refactorización asistida por IA (100 puntos): guarden su versión refactorizada en una carpeta `06_codigo_refactorizado/` aparte, sin sobrescribir este original.
