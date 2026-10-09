# Nómina y caja

En **Personal y reportes → Condiciones de nómina**, configure tarifa por hora, día,
semana o mes y, por separado, la frecuencia de cierre de cada persona.

- Semanal: sábado a viernes; cierre el viernes.
- Quincenal: cierre el 15 y el 30.
- Mensual: cierre el 30.
- En febrero, el cierre nominal del 30 se realiza el 28 o 29. Los registros del
  día 31 se incluyen en el período siguiente; no se pierde ese día de trabajo.

La fecha de cierre es independiente del porcentaje de base y de los abonos.
Una tarifa mensual se divide entre 30 y una semanal entre 7 para aplicar 7, 15 o
30 días nominales según la frecuencia. Las tarifas por hora usan minutos
aprobados; las diarias cuentan fechas distintas con trabajo aprobado. El
porcentaje permite liquidar una base parcial y queda guardado con la nómina.
Para un porcentaje individual, seleccione a esa persona. Un período procesado
no puede volver a procesarse para el mismo empleado, aunque cambie su frecuencia.

**Horas / acuerdo** añade importes autorizados separados de la base. Introduzca
cantidad, tarifa y justificación. No registre las mismas horas como ordinarias
y adicionales. No se calculan automáticamente recargos o deducciones legales.

En **Contratos por función y avance**, el monto liberado es el total actualizado
por el porcentaje acumulado, menos lo liberado anteriormente. Los cambios
conservan una auditoría. Lo liberado se incorpora una sola vez a la siguiente
nómina de la persona y aparece como obligación pendiente en la vista corporativa.
La persona necesita una frecuencia de nómina configurada; puede usar tarifa cero
para recibir únicamente importes de contrato.

**Caja y bancos** permite crear cuentas internas de caja chica y banco; registrar
capital, saldos iniciales y otros ingresos; y registrar transferencias entre ellas.
Los cobros de facturas se registran desde **Cuentas por cobrar** para que reduzcan
la deuda del cliente y aumenten la cuenta seleccionada en una sola operación.
No vuelva a introducir esos cobros como otros ingresos.

Los pagos de nómina aceptan abonos, fecha, referencia y cuenta de origen.
El estado muestra pendiente, pago parcial o pagada. Los pagos de gastos y de
nóminas de finca también seleccionan cuenta cuando la empresa tiene cuentas.
Se impiden pagos que superen la deuda o el saldo disponible. Las operaciones
bancarias reales se hacen fuera de Zero; aquí se registra el movimiento realizado.

Los registros antiguos se conservan sin inventar movimientos bancarios. Cargue
el saldo inicial real de cada cuenta. El exportador versión 6 incluye nómina,
contratos y tesorería y sigue admitiendo archivos anteriores.

## Datos bancarios y monedas

En Caja y bancos, **+ Cuenta** o **Editar datos** permite guardar banco, número de
cuenta (conservando ceros iniciales), titular, RNC/cédula, tipo de cuenta, moneda,
sucursal, país, SWIFT/BIC, IBAN y notas. Los datos internacionales son opcionales.
Las cuentas anteriores conservan sus saldos en DOP; puede completar sus datos.

Se admiten DOP, USD, EUR, CAD, GBP, CHF, MXN y COP. Ingresos, saldos iniciales y
transferencias entre cuentas se registran en la moneda seleccionada, sin cambio
automático. Una cuenta con movimientos no permite cambiar su moneda. Facturas,
gastos y nóminas actuales operan en DOP y seleccionan cuentas DOP. El formato de
exportación versión 7 incluye los datos bancarios y admite versiones anteriores.
