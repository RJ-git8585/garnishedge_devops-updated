# Garnishment Services

Modular architecture for garnishment calculations, breaking down the monolithic service into focused components.

## Services

- **BaseService** - Common utilities and validation
- **ConfigLoader** - Configuration data loading
- **FeeCalculator** - Garnishment fee calculations  
- **ResultFormatter** - Result standardization
- **GarnishmentCalculator** - Individual garnishment calculations
- **DatabaseManager** - Database operations
- **CalculationDataView** - Main orchestration service

## Usage

```python
from processor.services import CalculationDataView

service = CalculationDataView()
result = service.calculate_garnishment('child_support', record, config_data)
```

## Migration

The new `CalculationDataView` maintains backward compatibility with the original service while providing a modular architecture.