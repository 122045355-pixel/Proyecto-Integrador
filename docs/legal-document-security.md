# Modelo de seguridad documental legal

## Principios

- La base de datos y el almacenamiento de archivos son append-only: no se borra informacion ni archivos.
- La app movil nunca se conecta directo a MySQL; consume la API con JWT de usuario.
- Los archivos no se descargan desde movil. La API debe entregar vista protegida o streaming controlado.
- Las descargas web solo se autorizan para jueces y notarios, y siempre generan auditoria.
- Los documentos sensibles se clasifican y se autorizan por caso, participante, rol y accion.

## Roles del dominio

- `interesado`: consulta sus documentos personales y libelos propios.
- `testigo`: consulta su identificacion y libelos propios.
- `abogado`: consulta libelos de sus clientes asignados.
- `juez`: consulta casos activos y puede descargar en web si tiene permiso.
- `notario`: acceso completo y descarga web.
- `admin_ti`: administracion tecnica sin acceso implicito al contenido.

## Clasificacion de documentos

- `personal_sensitive`: INE, acta de nacimiento, RFC, comprobante de domicilio.
- `witness_id`: identificacion de testigos.
- `marriage_certificate`: acta de matrimonio.
- `libelo`: testimonio manuscrito, escaneo y transcripcion OCR.
- `trial_pdf`: documentos de juicio versionados.

## Flujo recomendado

1. Cargar archivo y registrar hash SHA-256.
2. Crear version inmutable en `document_versions`.
3. Si es libelo, crear `ocr_jobs`.
4. Someter a autorizacion en `approval_requests`.
5. Crear `signature_requests` cuando este aprobado.
6. Registrar firmas secuenciales o paralelas en `signature_events`.
7. Registrar toda vista, firma, aprobacion o descarga en `document_access_events`.
8. Mover a archivo profundo con `archive_records` sin borrar datos.

## Endpoints base

```http
POST /login
GET /api/perfil
GET /api/cases
GET /api/cases/{case_id}/documents
POST /api/cases/{case_id}/documents
POST /api/documents/{document_id}/versions
GET /api/documents/{document_id}/view
POST /api/documents/{document_id}/approval-requests
POST /api/approval-requests/{request_id}/approve
POST /api/documents/{document_id}/signature-requests
POST /api/signature-requests/{request_id}/sign
POST /api/cases/{case_id}/archive
```

## Restriccion de descarga

La API debe evaluar siempre:

- canal: `web` o `mobile`
- rol del usuario
- relacion con el caso/documento
- accion solicitada: `view`, `download`, `approve`, `sign`, `archive`

Regla inicial:

- `mobile + download` siempre se rechaza.
- `web + download` solo para `juez` y `notario`.
- cualquier descarga crea evento de auditoria.
