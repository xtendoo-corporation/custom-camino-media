# custom-camino-media

Personalizaciones de Odoo 19.0 para **Camino Media, S.L.** (https://caminomedia.xtd.es).

## custom_camino_media

Extiende el informe de factura **estándar** de Odoo (sin sustituirlo) para mostrar
los datos propios de Camino Media:

- `Location` / `Localización`
- `Shoot Dates` / `Fechas de rodaje`
- `Contact` / `Contacto`

Son campos de la factura (pestaña de cabecera) y salen en el bloque de información del
informe estándar, en el idioma del cliente (inglés o español).

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
