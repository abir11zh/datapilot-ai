"""Portable environment configuration. Only public_settings may reach the browser."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit


def local_endpoint(url: str) -> bool:
    return urlsplit(url).hostname in {'localhost', '127.0.0.1', '::1'}


def valid_url(url: str) -> bool:
    try:
        value = urlsplit(url)
        return bool(value.scheme in {'http', 'https'} and value.hostname and
                    not value.username and not value.password and not value.query and not value.fragment)
    except ValueError:
        return False


def load_env_file(path: str) -> None:
    """Opt-in .env reader; never executes shell syntax or overrides environment variables."""
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.strip().replace('_', '').isalnum():
            raise ValueError(f'Invalid environment assignment on line {number}.')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    mode: str = 'local'
    host: str = '127.0.0.1'
    port: int = 8501
    public_url: str = ''
    provider: str = 'ollama'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3:4b'
    remote_url: str = ''
    remote_model: str = ''
    remote_key: str = field(default='', repr=False)
    remote_format: str = 'json_object'
    timeout: int = 180
    max_upload_mb: int = 100
    max_sessions: int = 8
    session_ttl: int = 7200

    @classmethod
    def from_env(cls):
        env = os.environ
        mode = env.get('APP_MODE', 'local').lower()
        if mode not in {'local', 'cloud'}:
            raise ValueError('APP_MODE must be local or cloud.')
        public = env.get('PUBLIC_URL', '').rstrip('/')
        if public and (not valid_url(public) or urlsplit(public).path):
            raise ValueError('PUBLIC_URL must be an HTTP(S) origin without a path or credentials.')
        def integer(key, default, low, high):
            try:
                value = int(env.get(key, default))
                if low <= value <= high:
                    return value
            except ValueError:
                pass
            raise ValueError(f'{key} must be an integer between {low} and {high}.')
        return cls(mode=mode, host=env.get('HOST', '0.0.0.0' if mode == 'cloud' else '127.0.0.1'),
                   port=integer('PORT', 8501, 1, 65535), public_url=public,
                   provider=env.get('LLM_PROVIDER', 'remote' if mode == 'cloud' else 'ollama').lower(),
                   ollama_url=env.get('OLLAMA_BASE_URL', env.get('OLLAMA_HOST', 'http://127.0.0.1:11434')).rstrip('/'),
                   ollama_model=env.get('OLLAMA_MODEL', 'qwen3:4b'),
                   remote_url=env.get('REMOTE_LLM_BASE_URL', '').rstrip('/'),
                   remote_model=env.get('REMOTE_LLM_MODEL', ''), remote_key=env.get('REMOTE_LLM_API_KEY', ''),
                   remote_format=env.get('REMOTE_LLM_FORMAT', 'json_object'),
                   timeout=integer('LLM_TIMEOUT_SECONDS', 180, 5, 600),
                   max_upload_mb=integer('MAX_UPLOAD_MB', 100, 1, 250),
                   max_sessions=integer('MAX_SESSIONS', 8, 1, 100),
                   session_ttl=integer('SESSION_TTL_SECONDS', 7200, 60, 86400))

    @property
    def provider_problem(self):
        if self.provider == 'disabled':
            return 'AI is disabled for this workspace. Calculated analytics remain available.'
        if self.provider == 'ollama':
            return '' if valid_url(self.ollama_url) else 'Configure a valid OLLAMA_BASE_URL.'
        if self.provider == 'remote':
            if not self.remote_url or not self.remote_model or not self.remote_key:
                return 'Cloud AI is not configured. The host administrator must set REMOTE_LLM_BASE_URL, REMOTE_LLM_MODEL, and REMOTE_LLM_API_KEY.'
            if not valid_url(self.remote_url) or (not local_endpoint(self.remote_url) and not self.remote_url.startswith('https://')):
                return 'REMOTE_LLM_BASE_URL must use HTTPS (HTTP is allowed only for loopback testing).'
            if self.remote_format not in {'json_object', 'json_schema'}:
                return 'REMOTE_LLM_FORMAT must be json_object or json_schema.'
            return ''
        return 'LLM_PROVIDER must be ollama, remote, or disabled.'

    def public_settings(self):
        local_ai = self.provider == 'ollama' and local_endpoint(self.ollama_url)
        if self.mode == 'cloud':
            title, detail = 'Hosted analytics workspace', 'Files are processed on this server. Sessions are temporary.'
        elif local_ai or self.provider == 'disabled':
            title, detail = 'Analytics on this computer', 'Local processing. Real calculations.'
        else:
            title, detail = 'Local analytics · remote AI', 'Questions, schema and bounded result summaries go to the configured AI host.'
        return {'mode': self.mode, 'provider': self.provider,
                'model': self.ollama_model if self.provider == 'ollama' else self.remote_model,
                'ai_location': 'local' if self.mode == 'local' and local_ai else 'cloud',
                'privacy_title': title, 'privacy_detail': detail,
                'ai_disclosure': 'AI receives your questions, column schema, bounded conversation summaries and selected calculated findings. Full datasets are not sent. No automatic provider switching.',
                'max_upload_mb': self.max_upload_mb, 'session_ttl_seconds': self.session_ttl}
