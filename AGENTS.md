# AGENTS.md
<!-- Reglas basicas sustentas a cambios -->
## Proyecto
Se trata de un sistema multiagente de detección de fraude.

## Arquitectura
- A1 analiza las transcripciones de llamadas.
- A2 investiga patrones.
- A3 valida los patrones frente a datos históricos.
- A4 genera reglas de fraude.
- A5 realiza pruebas retrospectivas (*backtesting*) deterministas.

## Reglas de desarrollo
- No modificar directamente la rama principal (*main*).
- Seguir las especificaciones aprobadas.
- No inventar requisitos.
- Examinar el código existente antes de modificarlo.
- Ejecutar pruebas tras realizar cambios.
- No introducir dependencias innecesarias.

## Responsabilidades de la IA
- Kiro: especificación y planificación.
- Codex: implementación, depuración y pruebas.
- Se requiere aprobación humana antes de realizar cambios arquitectónicos.
