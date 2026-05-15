import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

OUTPUT_FILE = 'agh-mihomo-rules.txt'
HTML_LIKE_PREFIXES = (
    '<!doctype html',
    '<html',
    '<head',
    '<body',
    '<?xml',
)
VALID_GROUP_RE = re.compile(r'^[A-Za-z0-9_]+$')
YAML_RULE_RE = re.compile(r'^\s*-\s*(DOMAIN-SUFFIX|DOMAIN)\s*,\s*([^,\s#]+)', re.IGNORECASE)
LIST_MIHO_RULE_RE = re.compile(r'^(DOMAIN-SUFFIX|DOMAIN)\s*,\s*([^,\s#]+)', re.IGNORECASE)


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GroupConfig:
    name: str
    sources: list[str]
    dns_servers: str


@dataclass(frozen=True)
class ParsedRule:
    matcher: str  # exact | suffix
    domain: str
    source: str
    line_number: int


@dataclass
class DomainState:
    exact_dns: str | None = None
    suffix_dns: str | None = None
    subdomain_only_dns: str | None = None


def load_group_names() -> list[str]:
    raw = os.environ.get('RULESET_NAMES', '')
    names: list[str] = []
    seen: set[str] = set()
    for token in re.split(r'[\s,]+', raw.strip()):
        if not token:
            continue
        name = token.strip()
        if not VALID_GROUP_RE.fullmatch(name):
            raise ValidationError(
                'Invalid ruleset name {!r}. Use only letters, numbers, and underscores in RULESET_NAMES.'.format(name)
            )
        normalized = name.upper()
        if normalized in seen:
            raise ValidationError(f'Duplicate ruleset name in RULESET_NAMES: {name}')
        seen.add(normalized)
        names.append(name)

    if not names:
        raise ValidationError('RULESET_NAMES is required, for example: meta,google')

    return names


def split_non_empty_lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]



def normalize_dns_servers(raw: str, *, group_name: str) -> str:
    tokens = raw.split()
    if not tokens:
        raise ValidationError(f'DNS_{group_name.upper()} is required and cannot be empty')
    return ' '.join(tokens)



def load_default_dns() -> list[str]:
    raw = os.environ.get('DEFAULT_DNS', '')
    return [line.strip() for line in raw.splitlines() if line.strip()]



def load_group_config(name: str) -> GroupConfig:
    upper = name.upper()
    sources_raw = os.environ.get(f'DOMAIN_{upper}', '')
    dns_raw = os.environ.get(f'DNS_{upper}', '')

    sources = split_non_empty_lines(sources_raw)
    if not sources:
        raise ValidationError(
            f'DOMAIN_{upper} is required and must contain one or more .list/.yaml URLs, one per line'
        )

    dns_servers = normalize_dns_servers(dns_raw, group_name=name)
    return GroupConfig(name=name, sources=sources, dns_servers=dns_servers)



def normalize_source(source: str) -> str:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme not in ('http', 'https'):
        return source

    if parsed.netloc == 'github.com':
        parts = [part for part in parsed.path.split('/') if part]
        if len(parts) >= 5 and parts[2] == 'blob':
            owner, repo, _, ref = parts[:4]
            rest = '/'.join(parts[4:])
            return f'https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{rest}'

    return source



def fetch_text(source: str) -> str:
    source = normalize_source(source)
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ('http', 'https'):
        request = urllib.request.Request(source, headers={'User-Agent': 'agh-mihomo-rules/0.1'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                charset = response.headers.get_content_charset() or 'utf-8'
                return response.read().decode(charset, errors='replace')
        except urllib.error.URLError as exc:
            raise ValidationError(f'Failed to download {source}: {exc}') from exc

    path = Path(source)
    if path.is_file():
        return path.read_text(encoding='utf-8')

    raise ValidationError(f'Unsupported source or missing local file: {source}')



def validate_source_text(source: str, text: str) -> None:
    if not text.strip():
        raise ValidationError(f'Source is empty: {source}')

    lowered = text.lstrip().lower()
    if any(lowered.startswith(prefix) for prefix in HTML_LIKE_PREFIXES):
        raise ValidationError(f'Source looks like HTML, not a mihomo rules file: {source}')

    if lowered.startswith('404:') or lowered.startswith('not found'):
        raise ValidationError(f'Source looks like an error page: {source}')



def source_kind(source: str) -> str:
    path = urllib.parse.urlparse(source).path.lower()
    if path.endswith('.list'):
        return 'list'
    if path.endswith('.yaml') or path.endswith('.yml'):
        return 'yaml'
    raise ValidationError(f'Unsupported source type for {source}. Only .list, .yaml, and .yml are supported.')



def normalize_domain(domain: str, *, source: str, line_number: int) -> str:
    normalized = domain.strip().lower().strip('.')
    if not normalized:
        raise ValidationError(f'Empty domain in {source} line {line_number}')
    if any(ch.isspace() for ch in normalized):
        raise ValidationError(f'Invalid domain with spaces in {source} line {line_number}: {domain!r}')
    return normalized



def parse_list_rules(source: str, text: str) -> list[ParsedRule]:
    rules: list[ParsedRule] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        match = LIST_MIHO_RULE_RE.match(line)
        if match:
            matcher_name, domain_text = match.groups()
            matcher = 'suffix' if matcher_name.upper() == 'DOMAIN-SUFFIX' else 'exact'
            domain = normalize_domain(domain_text, source=source, line_number=line_number)
            rules.append(ParsedRule(matcher, domain, source, line_number))
            continue

        if line.startswith('+.'):
            domain = normalize_domain(line[2:], source=source, line_number=line_number)
            rules.append(ParsedRule('suffix', domain, source, line_number))
            continue

        if ',' in line:
            continue

        domain = normalize_domain(line, source=source, line_number=line_number)
        rules.append(ParsedRule('exact', domain, source, line_number))

    if not rules:
        raise ValidationError(f'No supported .list rules found in {source}')
    return rules



def parse_yaml_rules(source: str, text: str) -> list[ParsedRule]:
    rules: list[ParsedRule] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        match = YAML_RULE_RE.match(raw_line)
        if not match:
            continue
        matcher_name, domain_text = match.groups()
        matcher = 'suffix' if matcher_name.upper() == 'DOMAIN-SUFFIX' else 'exact'
        domain = normalize_domain(domain_text, source=source, line_number=line_number)
        rules.append(ParsedRule(matcher, domain, source, line_number))

    if not rules:
        raise ValidationError(f'No supported DOMAIN / DOMAIN-SUFFIX rules found in {source}')
    return rules



def parse_source_rules(source: str) -> list[ParsedRule]:
    text = fetch_text(source)
    validate_source_text(source, text)
    kind = source_kind(source)
    if kind == 'list':
        return parse_list_rules(source, text)
    return parse_yaml_rules(source, text)



def render_full(domain: str, dns_servers: str) -> list[str]:
    return [f'[/{domain}/]{dns_servers}']



def render_exact_only(domain: str, dns_servers: str) -> list[str]:
    return [f'[/{domain}/]{dns_servers}', f'[/*.{domain}/]#']



def render_exact_with_subdomains(domain: str, exact_dns: str, subdomain_dns: str) -> list[str]:
    if exact_dns == subdomain_dns:
        return render_full(domain, exact_dns)
    return [f'[/{domain}/]{exact_dns}', f'[/*.{domain}/]{subdomain_dns}']



def convert(groups: list[GroupConfig], default_dns_lines: list[str]) -> tuple[list[str], dict[str, int]]:
    states: OrderedDict[str, DomainState] = OrderedDict()
    stats = {
        'groups': len(groups),
        'sources': 0,
        'default_dns_lines': len(default_dns_lines),
        'parsed_rules': 0,
        'accepted_exact': 0,
        'accepted_suffix': 0,
        'accepted_subdomain_only': 0,
        'skipped_exact_conflicts': 0,
        'skipped_suffix_conflicts': 0,
    }

    for group in groups:
        for source in group.sources:
            stats['sources'] += 1
            for rule in parse_source_rules(source):
                stats['parsed_rules'] += 1
                state = states.setdefault(rule.domain, DomainState())

                if rule.matcher == 'exact':
                    if state.suffix_dns is not None or state.exact_dns is not None:
                        stats['skipped_exact_conflicts'] += 1
                        continue
                    state.exact_dns = group.dns_servers
                    stats['accepted_exact'] += 1
                    continue

                if state.suffix_dns is not None:
                    stats['skipped_suffix_conflicts'] += 1
                    continue

                if state.exact_dns is not None:
                    if state.subdomain_only_dns is None:
                        state.subdomain_only_dns = group.dns_servers
                        stats['accepted_subdomain_only'] += 1
                    else:
                        stats['skipped_suffix_conflicts'] += 1
                    continue

                state.suffix_dns = group.dns_servers
                stats['accepted_suffix'] += 1

    lines: list[str] = list(default_dns_lines)
    for domain, state in states.items():
        if state.suffix_dns is not None:
            lines.extend(render_full(domain, state.suffix_dns))
            continue

        if state.exact_dns is None:
            continue

        if state.subdomain_only_dns is None:
            lines.extend(render_exact_only(domain, state.exact_dns))
            continue

        lines.extend(render_exact_with_subdomains(domain, state.exact_dns, state.subdomain_only_dns))

    if not lines:
        raise ValidationError('No output rules were generated')

    return lines, stats



def main() -> int:
    groups = [load_group_config(name) for name in load_group_names()]
    default_dns_lines = load_default_dns()
    lines, stats = convert(groups, default_dns_lines)

    converted_directory = Path.cwd() / 'converted'
    converted_directory.mkdir(exist_ok=True)
    output_path = converted_directory / OUTPUT_FILE
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(
        'groups: {groups}, sources: {sources}, default dns lines: {default_dns_lines}, parsed rules: {parsed_rules}, '
        'accepted exact: {accepted_exact}, accepted suffix: {accepted_suffix}, '
        'accepted subdomain-only: {accepted_subdomain_only}, '
        'skipped exact conflicts: {skipped_exact_conflicts}, '
        'skipped suffix conflicts: {skipped_suffix_conflicts}, '
        'output lines: {output_lines}'.format(
            output_lines=len(lines),
            **stats,
        )
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
