# Primer acceso administrador

Si la base de datos esta vacia, `POST /api/users` no funciona porque todavia no existe un JWT de `admin` o `admin_ti`. Para resolver el arranque inicial existe un endpoint de bootstrap.

## Crear el primer administrador

Este endpoint solo funciona mientras `users` esta vacia. Despues queda bloqueado con `409`.

```bash
curl -X POST "http://localhost:8004/api/bootstrap/admin" \
  -H "x-api-key: ABC123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emiliano",
    "email": "emiliano.figueroa4@outlook.com",
    "password": "Emiliano4"
  }'
```

La respuesta incluye `access_token`. Copialo y usalo como:

```text
Authorization: Bearer TU_ACCESS_TOKEN
```

## Crear usuarios despues del bootstrap

Una vez autenticado como `admin_ti`, ya puedes usar:

```http
POST /api/users
```

con headers:

```http
x-api-key: ABC123
Authorization: Bearer TU_ACCESS_TOKEN
Content-Type: application/json
```

Ejemplo:

```json
{
  "name": "Juez Demo",
  "email": "juez@example.com",
  "password": "Juez1234",
  "role_id": 4
}
```

## Consultar roles disponibles

```bash
curl -X GET "http://localhost:8004/api/roles" \
  -H "x-api-key: ABC123" \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

## Nota importante

Si ya levantaste MySQL antes de agregar estos cambios, el script `mysql/init.sql` no se vuelve a ejecutar automaticamente porque el volumen `mysql_data` ya existe. En ese caso aplica manualmente las migraciones o reinicia el volumen solo si no necesitas conservar datos.
