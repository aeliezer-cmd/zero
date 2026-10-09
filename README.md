# Zero · piloto local de Calidad de Vida

Guía de cierres, contratos por avance y cuentas de caja/banco: [Nómina y caja](NOMINA-Y-CAJA.md).

Aplicación funcional en español para un piloto supervisado. Python 3.9 o posterior, SQLite y navegador; no necesita instalar paquetes ni conexión a internet. Los archivos de interfaz son locales. No es una aplicación de tienda: admite operación de urbanización, personal, proyectos, gastos y servicios contratados.

## Iniciar y acceder

En macOS, abra **Iniciar.command**. También puede usar una terminal:

```sh
cd /Users/user/Documents/Zero
python3 app.py
```

Abra **http://127.0.0.1:8000**. Mantenga la terminal y el equipo encendidos. Para detener: Ctrl+C. Al reiniciar se conservan los datos y se requiere volver a iniciar sesión.

Las contraseñas iniciales aleatorias están en `data/ACCESOS.txt` (archivo privado local):

- `demo`: dos empresas ficticias, para practicar y ver el consolidado corporativo.
- `monarca`: Calidad de Vida real, sin personas, clientes ni movimientos inventados. Departamentos y proyecto iniciales configurados.

Cambie su contraseña en Configuración. No comparta `ACCESOS.txt`. El archivo conserva solo la contraseña inicial, no las posteriores. Los usuarios de una empresa se crean desde Configuración.

## Registro e intercambio de datos desde la aplicación

En la pantalla inicial hay tres opciones:

- **Iniciar sesión**: entrar con el usuario autorizado y seleccionar su empresa. No se muestran empresas privadas antes de autenticar.
- **Crear empresa**: registrar nombre de empresa, administrador, usuario y clave (mínimo cuatro caracteres). Crea una empresa vacía y aislada. Puede marcarla como demostración. No permite apropiarse de una cuenta o empresa existente.
- **Importar empresa**: seleccionar un archivo `.zero.json`, revisar nombre y cantidad de registros, elegir un nombre libre para la copia y crear su nuevo administrador. Guarda todo en una única transacción; si hay un error no se crea ni la empresa ni el usuario. Los archivos ya importados se rechazan para evitar duplicados.

Para exportar, un administrador entra en **Configuración → Exportar empresa**. Se descarga solamente la empresa activa: departamentos, proyectos, clientes, catálogo, servicios, cargos, pagos, personal, reportes, tareas, gastos y su historial. Los autores históricos se conservan como identidades sin acceso. No incluye contraseñas, sesiones ni permisos de usuarios: el nuevo administrador asigna accesos después de importar.

La importación crea una copia independiente; **no combina ni reemplaza** empresas existentes. Mantiene el carácter demo/real de origen. No acepta archivos SQLite, Excel ni formatos de otros programas. Límite: 50 MB y 50,000 registros. Las referencias y los saldos se validan en el servidor. El registro/importación inicial solo está habilitado desde el equipo del servidor.

El archivo exportado contiene datos privados sin cifrar. Consérvelo como respaldo de esa empresa. Para recuperar además todas las cuentas y empresas del programa, use el respaldo completo SQLite documentado más abajo. Ninguna de estas funciones sincroniza cambios entre equipos.

## Recorrido sugerido para mañana

1. Entre primero con `demo`. El aviso DEMO permanece visible; todos sus movimientos son ficticios.
2. En **Vista corporativa**, aplique un período y revise resultados de las dos empresas y consolidados.
3. En **Cobros y servicios → Clientes**, cree un cliente; en **Catálogo**, un producto o servicio.
4. Use **Contratar servicio**: cargo único, cada N días o cada N meses; inicio, fin opcional e importe. El plazo de cobro son días desde cada inicio de período, independiente del fin del servicio.
5. Se generan los períodos iniciados hasta hoy al contratar. Al iniciar cada jornada pulse **Generar períodos hasta hoy**; puede hacerlo varias veces sin duplicar cargos. No hay un proceso de generación en segundo plano.
6. En **Cargos y alertas**, registre un pago parcial con su fecha real y referencia. Observe saldo y estado; revise **Pagos recibidos**.
7. Registre un gasto, apruébelo y registre su pago. Cree una ficha de personal, un reporte de supervisión y una tarea con responsable.
8. Cree un usuario básico o revisor, configure nombre del rol y alcance; cierre sesión y compruebe su experiencia.
9. Para datos verdaderos, cierre sesión e ingrese con `monarca`. Verifique el distintivo **EMPRESA REAL** antes de registrar.
10. Al terminar, ejecute **Respaldar.command** y conserve una copia segura fuera del equipo.

El demo incluye ejemplos iniciales y algunos registros ficticios marcados “prueba de navegador · DEMO”, usados para verificar el flujo.

## Qué está implementado

- Inicio de sesión, contraseñas PBKDF2 con sal individual, sesiones de ocho horas en memoria, cookies HttpOnly/SameSite, protección CSRF y limitación básica de intentos.
- Autorización en servidor: cada consulta y escritura exige membresía en la empresa. Ser administrador no concede acceso a empresas ajenas.
- Niveles acumulativos: básico registra, revisor además aprueba y registra pagos, administrador además configura. Los nombres de rol son libres.
- Alcance de departamentos y proyectos configurable por usuario para operación. Sin selecciones significa todos; al seleccionar ambos, se aplica la intersección. Registros sin asignar no aparecen a usuarios de alcance restringido.
- Permiso de cobros independiente, de alcance **empresarial**: habilita clientes, catálogo, contratos, cargos, pagos y alertas. Un usuario limitado por departamento con permiso de cobros sí ve todos los cobros de su empresa; el formulario lo indica. Administradores siempre lo tienen.
- Clientes, productos/servicios y contratación única o recurrente; mensualidades con ancla al día original: 31 de enero → 28/29 de febrero → 31 de marzo.
- Cargos únicos por contrato/período mediante restricción de base de datos. Pago parcial, saldo, pendiente, pagado y vencido. Importes guardados como centavos enteros. Operaciones de pago con clave idempotente y transacción serializada contra sobrepagos concurrentes.
- Cancelación conserva el historial y los saldos, genera lo ya devengado y detiene cargos futuros. La fecha de fin del servicio es inclusiva para el inicio del último período; no hay prorrateos.
- Alertas internas para los próximos cinco días, el día anterior, el día de vencimiento y vencidos. Se calculan al cargar/actualizar; son comunes para usuarios con permiso, no dependen del creador. No hay push, mensajes externos ni cobro bancario. “24 horas” significa **el día calendario anterior**, ya que el piloto usa fechas sin hora de vencimiento; se usa America/Santo_Domingo.
- Gastos propuestos/aprobados, referencia de comprobante y pagos parciales. Los comprobantes se adjuntan como fotos o documentos desde cada registro.
- Personal con condición mensual/diaria/horaria propuesta, reportes con minutos, actividad, método y observaciones/evidencias de referencia; aprobación de reportes.
- Tareas, responsables, fechas, estados y texto de departamentos participantes/apoyo. El apoyo no extiende permisos ni envía solicitudes externas.
- Preparación de nómina: referencia aritmética de tarifa horaria × tiempo aprobado. No se transforma en nómina aprobada o pagada. Mensuales, diarios e híbridos requieren cálculo/revisión fuera de este piloto.
- Registro transaccional inmediato e historial de creaciones, aprobaciones, cancelaciones, pagos y permisos. No se borran movimientos desde la aplicación.

## Definiciones del panel corporativo

El panel muestra solo las empresas que el usuario tiene autorizadas; demo y reales se consolidan por separado. La etiqueta de grupo es organizativa, nunca una concesión de acceso. Usuarios de alcance limitado ven los importes operativos correspondientes a ese alcance.

| Métrica | Definición |
| --- | --- |
| Gastos aprobados | Gastos actualmente aprobados cuya fecha cae en el período. |
| Pagos pendientes | Saldo acumulado de gastos aprobados fechados hasta el fin del período, descontando pagos hasta ese día. |
| Cobrado | Pagos de clientes fechados dentro del período. Generar un cargo no es cobro. |
| Por cobrar | Cargos iniciados hasta el fin del período menos pagos fechados hasta ese día. Incluye cargos aún no vencidos. |
| Horas aprobadas | Minutos de reportes actualmente aprobados, con fecha en el período, divididos entre 60. |
| Tareas atrasadas | Tareas actualmente abiertas con fecha límite anterior a hoy; no reconstruye estados históricos. |

El panel informa período y fecha de actualización. Las aprobaciones son las actuales: no es un libro mayor ni una reconstrucción contable histórica. Cuando no hay permiso de cobros, esos datos quedan ocultos y fuera del consolidado visible. Todos los importes usan RD$, sin impuestos ni facturación fiscal.

## Respaldo y recuperación

La base activa es `data/zero.sqlite3`; puede tener archivos auxiliares WAL/SHM. **No sincronice esa base activa con Google Drive, Dropbox o similares.** Un respaldo es distinto de sincronización.

Abra **Respaldar.command** o ejecute:

```sh
python3 app.py --backup respaldos/zero-2026-09-22.sqlite3
```

La herramienta usa la API de respaldo consistente de SQLite y puede ejecutarse con el servidor activo. El archivo resultante incluye **todas las empresas y usuarios**: manténgalo privado. No hay respaldo automático ni integración con Drive; puede copiar manualmente el respaldo cerrado a un destino seguro. Las contraseñas se guardan como hashes, pero los demás datos no están cifrados por la aplicación.

Para restaurar, detenga el servidor; conserve la carpeta `data` actual renombrándola antes de reemplazarla. Cree una carpeta `data` nueva y copie el respaldo dentro con el nombre `zero.sqlite3`; no copie archivos WAL/SHM antiguos. Restrinja permisos de carpeta a 700 y del archivo a 600. Inicie el servidor y verifique sus datos. Las contraseñas serán las del momento del respaldo.

## Administración de empresas (herramienta local)

Esta herramienta requiere acceso al sistema de archivos del equipo. No se expone a usuarios web. La agrupación corporativa es opcional, y una membresía explícita siempre es necesaria:

```sh
python3 manage.py list
python3 manage.py company "Otra empresa" --group "Grupo autorizado"
# Use el ID real que devuelve el comando anterior:
python3 manage.py grant monarca ID_EMPRESA --role admin --role-name "Administrador" --collections
python3 manage.py reset-password monarca
```

`grant` concede toda la empresa sin restricción departamental/proyecto y reemplaza los permisos previos de esa membresía. Para alcances parciales, configure después el usuario desde un administrador distinto en la interfaz. No mezcle usuarios de demo y reales. El grupo no implica jerarquía ni permite ver otras empresas automáticamente.

## Límites y trabajo posterior

Preparado para **piloto local supervisado**, no para publicación en internet sin una revisión adicional. No incluye HTTPS, recuperación por correo, MFA, almacenamiento cifrado, política de retención, migraciones versionadas, exportaciones contables fiscales, conciliación, corrección/anulación de pagos, nómina legal, licencias comerciales, Google Drive ni sincronización desconectada. Los registros operativos y financieros se crean y transicionan, pero todavía no tienen edición general: revise antes de guardar y use el demo para ensayar. Los errores en movimientos reales requieren una corrección controlada con respaldo previo; no modifique la base a ciegas.

Los dos puestos (cocina y atención de visitantes), la propuesta de RD$22,000, horario 2–9 pm y días libres **no se precargan como contratos validados**. Falta asignación y validación laboral. La forma de pago o el nombre “contratista” no determina la relación laboral. Entrega de uniformes queda pendiente.

La misma base y servidor pueden prepararse para intranet, pero por defecto escuchan solo en `127.0.0.1`. No ejecute `--host 0.0.0.0` con datos sensibles sin preparar transporte seguro y acceso de red. Para producción se requiere reemplazar/endurecer el servidor HTTP, operar respaldos y seguridad, y definir destino de alojamiento. Este piloto no se ha desplegado públicamente.

## Verificación

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile app.py manage.py
node --check static/app.js
```

Las pruebas utilizan una base temporal separada, sin modificar datos reales: autenticación/CSRF, aislamiento, herencia de permisos, alcance, referencias entre empresas, meses cortos, cada N días, idempotencia, pagos parciales/concurrentes, aprobación, alertas compartidas, zona horaria, cancelación, caja vs. facturación, historial, persistencia y respaldo consistente. La interfaz se verificó en navegador con datos DEMO.

## Reportes y apariencia

La sección **Reportes** permite consultar gastos, horas de trabajo, tareas, cargos y pagos recibidos por período, estado y búsqueda. Los registros operativos admiten departamento y proyecto, y las horas/tareas admiten persona o responsable. Se puede elegir “Sin asignar”. Al generar, se actualizan los datos del servidor respetando los permisos de la empresa activa; el filtro no amplía el alcance autorizado.

El período se aplica a la fecha del gasto, del trabajo, límite de tarea, vencimiento del cargo o fecha efectiva del pago según el reporte. Los saldos y estados son actuales, no históricos. Los cobros no tienen departamento/proyecto en este modelo y no presentan esos filtros. El detalle incluye totales, resumen departamental, descarga CSV e impresión para guardar como PDF mediante el navegador. El CSV protege las celdas de texto que podrían interpretarse como fórmulas.

El botón **Tema oscuro / Tema claro** está en la pantalla inicial y en la barra superior. Conserva la preferencia en ese navegador después de recargar o cerrar sesión. Los reportes se imprimen con fondo claro independientemente del tema.

Pruebas adicionales de reportes: `node tests/test_reports.js`.

## Facturas y comprobantes adjuntos

Use **Adjuntos** en un gasto, pago de gasto, cargo pendiente de cobro o pago recibido. Primero guarde el movimiento, luego seleccione una o varias fotos/documentos y pulse **Subir archivos**. Los pagos de gastos tienen su propio listado debajo del registro de gastos.

Formatos: JPG/JPEG, PNG, WebP, HEIC/HEIF, PDF y DOCX. Límite: 5 MB por archivo y 25 MB por empresa en este piloto. Las fotos JPG/PNG/WebP tienen vista previa; los demás archivos se descargan para abrirlos con una aplicación compatible. Cada archivo se valida y guarda en una transacción; si falla uno de varios, la pantalla indica cuántos quedaron guardados. Reintentar no duplica el mismo contenido en el mismo registro.

Los adjuntos exigen sesión y los permisos de la empresa y registro tanto para listarlos como para verlos/descargarlos. Se conservan nombre, fecha, tamaño y huella de contenido en el historial. Adjuntar un comprobante no aprueba un gasto ni confirma un cobro. No incluye lectura automática/OCR de facturas ni borrado de comprobantes.

Los archivos se guardan dentro de SQLite: están incluidos en el respaldo completo y en la exportación `.zero.json` de la empresa (formato versión 2). La importación también acepta archivos antiguos de versión 1 sin adjuntos. No se sincronizan con Google Drive.


## Fincas, ventas y nóminas

En **Fincas y nóminas**, el administrador crea fincas asignadas a departamentos/proyectos. Los usuarios solo ven las fincas y trabajadores dentro de su alcance. Ventas exige permiso de cobros; contratos, aprobación y nóminas exigen revisor o administrador.

Registre ventas con producto, cantidad, unidad, precio, comprador, vendedor e importe recibido inicialmente. El resumen muestra ventas e ingresos recibidos por finca y distingue cacao. No registre otra venta para reflejar un cobro posterior. Este módulo no integra aún cobros posteriores, devoluciones ni el consolidado de Vista corporativa.

Cree la ficha de personal antes del contrato. Los contratos aceptan ajuste o temporal, con pago fijo, por unidad, jornal u hora. Un ajuste fijo permite un trabajo completo de cantidad 1. Los trabajos usan la tarifa del contrato; se aprueban antes de generar la nómina. Cada nómina corresponde a siete días consecutivos ya terminados y una finca. Cada trabajo puede incluirse una sola vez. Las nóminas muestran importes brutos sin cálculo de impuestos/deducciones, y la confirmación de pago exige referencia.

En Gastos, un revisor puede **Editar factura** con motivo obligatorio. Se conservan pagos y adjuntos; no se permite reducir el total por debajo de los pagos ni fechar el gasto después del primer pago. Las correcciones quedan en auditoría.

Los respaldos SQLite incluyen los nuevos módulos. La exportación de empresa usa formato 3 y admite importar archivos anteriores (versiones 1 y 2). Regenere los paquetes compilados para incluir agriculture.py y la interfaz actual.


## Empresa, catálogo y documentos comerciales

La vista corporativa muestra la empresa seleccionada. El administrador edita nombre, RNC/identificación, teléfono, correo, dirección y logo en Configuración → Datos de la empresa. Los logos admiten PNG, JPEG o WebP de hasta 500 KB.

Cobros y servicios → Catálogo permite buscar productos, añadir cantidades a una factura, elegir cliente y vencimiento, y emitir una cuenta por cobrar. Los precios se toman del catálogo y se conservan en la factura junto con los datos de empresa y cliente del momento. Las facturas emitidas son documentos comerciales, sin numeración fiscal ni cálculo tributario.

En Cargos y alertas registre pagos parciales o completos. Cada pago tiene su Recibo / PDF en Pagos recibidos. Abra la factura o el recibo y use imprimir → Guardar como PDF. Estos cargos y pagos alimentan los reportes y los indicadores corporativos existentes. Los servicios periódicos conservan su flujo.

Descargar CSV o Imprimir/PDF aplica los filtros visibles de Reportes, aunque no se haya pulsado Generar reporte antes. Los cambios de tipo conservan el período y la búsqueda. Exportaciones de empresa: formato 4; importación compatible con 1, 2 y 3.
