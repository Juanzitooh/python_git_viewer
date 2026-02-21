# Checklists de release

Arquivos base (modelo):
- `CHECKLIST_FUNCIONAL_BASE.md`
- `CHECKLIST_DISTRIBUICAO_BASE.md`

Arquivos gerados automaticamente pelo `dist.sh`:
- `CHECKLIST_FUNCIONAL_<versao>.md`
- `CHECKLIST_DISTRIBUICAO_<versao>.md`

Regra:
- arquivos ja existentes nao sao sobrescritos (seguro para reinstall da mesma versao).
- `dist.sh` preenche automaticamente metadados basicos da maquina (data, tester, branch/commit, OS/distro/kernel).
