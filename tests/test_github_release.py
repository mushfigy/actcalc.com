"""GitHub-to-Render deploy must remain gated and have durable database storage."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]

def test_render_is_not_a_disposable_sqlite_instance():
    deploy=yaml.safe_load((ROOT/'render.yaml').read_text())
    assert len(deploy['services'])==1
    service=deploy['services'][0]
    assert service['runtime']=='docker'
    assert service['plan']!='free' # Free instances discard the SQLite database.
    assert service['disk']['mountPath']=='/data'
    assert service['disk']['sizeGB']>=1
    assert service['autoDeployTrigger']=='checksPass'
    assert service['healthCheckPath']=='/api/health'
    settings={item['key']:item for item in service['envVars']}
    assert settings['ACTCALC_PUBLIC']['value']=='false'
    assert settings['ACTCALC_ALLOW_LOCAL_DEV']['value']=='false'
    assert settings['ACTCALC_DB_PATH']['value'].startswith('/data/')
    for flag in ('ACTCALC_LEGAL_REVIEW_CONFIRMED','ACTCALC_SMTP_DELIVERY_VERIFIED','ACTCALC_BACKUP_RESTORE_VERIFIED','ACTCALC_LIVE_DEVICE_VERIFIED'):
        assert settings[flag]['value']=='false'
    for secret in ('ACTCALC_CONTACT_SECRET','ACTCALC_ADMIN_TOKEN','ACTCALC_PREVIEW_TOKEN'):
        assert settings[secret].get('generateValue') is True
    for secret in ('ACTCALC_SMTP_PASSWORD','ACTCALC_SMTP_USER'):
        assert settings[secret].get('sync') is False

def test_source_and_runtime_are_complete():
    docker=(ROOT/'Dockerfile').read_text()
    assert 'RUN python build_frontend.py' in docker
    assert 'COPY --from=frontend-builder' in docker
    assert 'COPY backend/' in docker
    assert '${PORT:-10000}' in docker
    assert '.env' in (ROOT/'.dockerignore').read_text()
    assert (ROOT/'static'/'index.html').exists()
    assert 'globalThis.ACTOfflineReview=(location.protocol' in (ROOT/'static'/'index.html').read_text()
