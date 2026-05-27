In case an encryption key is not created it can be created with the command (Veault encryption)

```python
python -c "from vault_encryption import generate_key, save_key; save_key(generate_key()); print('✓ Key generated and saved to .vault.key')"
```