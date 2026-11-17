# custom-camino-media

Personalizaciones de Odoo 19.0 para **Camino Media, S.L.** (https://caminomedia.xtd.es).

## camino_media_report

Extiende el informe de factura **estándar** de Odoo (sin sustituirlo) para mostrar
los datos propios de Camino Media:

- `Location` / `Localización`
- `Shoot Dates` / `Fechas de rodaje`
- `Contact` / `Contacto`

Son campos de la factura (pestaña de cabecera) y salen en el bloque de información del
informe estándar, en el idioma del cliente (inglés o español).

Además, en la versión 19.0.3.0.0:

- Etiquetas bilingües EN + ES en la factura (español en cursiva, gris y pequeño).
- Líneas: concepto en negrita, descripción del trabajo entre paréntesis y traducción en gris.
- Solo columnas Descripción e Importe.
- Marca de la factura (PSN o Camino Media) con logos en Compañía › Invoice Branding.
- Tipo de proyecto (filtros y agrupación), código de proyecto, orden de compra.
- Campos internos (no se imprimen): origen del trabajo (factura y líneas) y nota interna.
- Cuenta bancaria en la cabecera, elegida según la moneda, y aviso de pago en rojo y negrita.
- Seguidores de facturas configurables en la compañía.

Versión 19.0.4.0.0 (pendiente de subir): informe de factura propio de Camino Media
(`report_camino_invoice_document`), usado para facturas y rectificativas de cliente mediante
`_get_name_invoice_report`; la plantilla estándar queda intacta para el resto de documentos.
Los textos de pago (instrucciones, aviso de cuenta y caja roja de comisiones) se configuran
en cada cuenta bancaria. Código de proyecto y origen del trabajo también por línea.

Las cuentas bancarias de la compañía deben estar marcadas como *de confianza*
(`allow_out_payment`); si no, Odoo las borra al confirmar la factura.

El resto (pie de documento con registro mercantil y datos bancarios, logo, condiciones,
formato de papel) se gestiona con la **configuración de Odoo**, no con código:

- Ajustes › Compañías: logo, teléfono, email, **pie de informe** (`report_footer`,
  traducible por idioma).
- Contabilidad › Ajustes: condiciones y términos por defecto.

## Uso en Doodba

`odoo/custom/src/repos.yaml`:

```yaml
./custom-camino-media:
  defaults:
    depth: $DEPTH_DEFAULT
  remotes:
    xtendoo: https://github.com/xtendoo-corporation/custom-camino-media.git
  target: xtendoo 19.0
  merges:
    - xtendoo 19.0
```

`odoo/custom/src/addons.yaml`:

```yaml
custom-camino-media: ["*"]
```
