# Modbus HAS Binary Sensor

## Konfiguracja

### Przykład konfiguracji w `configuration.yaml`:

```yaml
modbushas:
  binary_sensor:
    - platform: modbushas
      hub: fatek
      scan_interval: 5
      coils:
        - name: "Drzwi garażu"
          coil: 100
          unique_id: "garage_door_sensor"
        - name: "Czujnik ruchu kuchnia"
          coil: 101
          # unique_id zostanie wygenerowany automatycznie
        - name: "Czujnik dymu salon"
          coil: 102
          unique_id: "smoke_detector_salon"
```

### Parametry konfiguracji:

- **platform**: Musi być `"modbushas"`
- **hub**: Nazwa hub'a Modbus (domyślnie `"fatek"`)
- **scan_interval**: Interwał odczytu w sekundach (domyślnie 30)
- **coils**: Lista czujników binarnych
  - **name**: Nazwa czujnika
  - **coil**: Adres coila Modbus
  - **unique_id**: Opcjonalny unikalny ID (jeśli nie podano, zostanie wygenerowany automatycznie)

## Funkcje

- **Asynchroniczne operacje**: Wykorzystuje nowoczesne API Home Assistant
- **Cache**: Inteligentny cache dla poprawy wydajności
- **Unique ID**: Każda encja ma unikalny identyfikator
- **Weryfikacja**: Opcjonalna weryfikacja po zapisie
- **Debug**: Rozbudowane logowanie dla diagnostyki

## Metody debugowania

Każda encja ma metody debugowania:

```python
# W konsoli Home Assistant:
entity = hass.states.get('binary_sensor.drzwi_garazu')
entity.attributes.get('debug_sensor_state')()
entity.attributes.get('get_cache_info')()
entity.attributes.get('force_refresh_state')()
```
