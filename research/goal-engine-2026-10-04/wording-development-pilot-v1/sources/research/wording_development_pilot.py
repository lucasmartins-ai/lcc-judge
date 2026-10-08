"""Data-only development pilot: eight hard fields, four within-tool distinctions.

Reuse original audited train/validation captures and generator/independent row
inspector. New goal aliases are separate whole authored phrases by split; record
caption vocabulary remains known. All18 fields remain in semantic UNKNOWN cases.
No old final rows/captures, tools, model inference, fitting or adoption.
"""

import argparse
import copy
import json
from pathlib import Path

from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_relation_state_supervision import inspect_row, digest, rows
from research.audit_tool_relation_states import audit as audit_raw
from research.detached_varied_study import now, save
from research.tool_relation_state_supervision import build_rows, write_rows

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT/'research/goal-engine-2026-10-04/tool-relation-states-v2'
OUT = DEVELOPMENT.parent/'wording-development-pilot-v1'
REQUESTS = {'train':dict(seed=442601,fixtures=64),'validation':dict(seed=442602,fixtures=32)}
PAIRS = {
    'pilot:retry_attempts:retry_failures':['retry_attempts','retry_failures'],
    'pilot:retry_actual_sleep_ns:retry_scheduled_sleep_ns':['retry_actual_sleep_ns','retry_scheduled_sleep_ns'],
    'pilot:udp_sent_datagrams:udp_sent_payload_bytes':['udp_sent_datagrams','udp_sent_payload_bytes'],
    'pilot:git_index_edits:git_worktree_edits':['git_index_edits','git_worktree_edits'],
}

# Four independently authored meanings per split/language; no suffix clones.
# Each field is still the same measured primitive, not a new domain or outcome.
ALIASES = {
    'retry_attempts': {
        'train': {
            'en': ('operation calls including every failed and successful retry', 'invocations before the retry returned or exhausted', 'attempt count at termination of Retrying', 'times the protected function was actually entered'),
            'pt': ('chamadas da operação incluindo cada retry com falha ou sucesso', 'invocações até o retry retornar ou esgotar as tentativas', 'contagem de tentativas ao término do Retrying', 'vezes em que a função protegida foi de fato executada')},
        'validation': {
            'en': ('all executions of the operation in this completed retry', 'how often the retried function ran before termination', 'calls from the initial try through the terminating try', 'final attempt ordinal observed for this invocation'),
            'pt': ('todas as execuções da operação neste retry encerrado', 'quantas vezes a função repetida rodou antes do término', 'chamadas desde a tentativa inicial até a tentativa final', 'ordinal da última tentativa observado nesta invocação')}},
    'retry_failures': {
        'train': {
            'en': ('retry operation calls that raised an exception', 'unsuccessful tries counted before retry termination', 'exceptions raised by the protected operation during Retrying', 'failed operation invocations rather than all attempts'),
            'pt': ('chamadas da operação de retry que lançaram uma exceção', 'tentativas malsucedidas contadas antes do término do retry', 'exceções lançadas pela operação protegida durante o Retrying', 'invocações com falha da operação em vez de todas as tentativas')},
        'validation': {
            'en': ('tries ending by raising rather than returning', 'number of operation exceptions in the completed retry', 'attempts without a successful operation result', 'failed-call count excluding any final successful call'),
            'pt': ('tentativas encerradas com exceção em vez de retorno', 'número de exceções da operação no retry encerrado', 'tentativas sem resultado bem-sucedido da operação', 'contagem de chamadas com falha excluindo uma chamada final bem-sucedida')}},
    'retry_scheduled_sleep_ns': {
        'train': {
            'en': ('nanoseconds requested by wait_fixed across retry pauses', 'prescribed waiting intervals added in nanoseconds', 'nominal retry delay budget rather than measured waiting time', 'total assigned wait duration expressed in nanoseconds'),
            'pt': ('nanossegundos solicitados pelo wait_fixed nas pausas do retry', 'intervalos de espera prescritos somados em nanossegundos', 'tempo nominal de espera do retry em vez da duração medida', 'duração total de espera atribuída expressa em nanossegundos')},
        'validation': {
            'en': ('sum of prescribed delays expressed in nanoseconds', 'policy-requested time for the retry waiting callbacks', 'scheduled nanosecond total independently of callback runtime', 'planned pause duration across the retry expressed in nanoseconds'),
            'pt': ('soma dos atrasos prescritos expressa em nanossegundos', 'tempo solicitado pela política aos callbacks de espera do retry', 'total programado de nanossegundos independentemente da duração dos callbacks', 'duração planejada das pausas do retry expressa em nanossegundos')}},
    'retry_actual_sleep_ns': {
        'train': {
            'en': ('nanoseconds measured inside sleeper callback executions', 'elapsed waiting-callback time without operation runtime', 'monotonic durations of the invoked sleeper functions in nanoseconds', 'actual time spent in retry waiting callbacks expressed in nanoseconds'),
            'pt': ('nanossegundos medidos dentro das execuções dos callbacks de espera', 'tempo decorrido nos callbacks de espera sem a execução da operação', 'durações monotônicas das funções de espera invocadas em nanossegundos', 'tempo efetivamente gasto nos callbacks de espera do retry em nanossegundos')},
        'validation': {
            'en': ('sum of sleeper entry-to-exit measurements in nanoseconds', 'observed retry pause runtime expressed in nanoseconds', 'time measured around waiting-function calls rather than their requested budget', 'measured nanoseconds in the waiting callbacks excluding operation calls'),
            'pt': ('soma das medições entre entrada e saída da espera em nanossegundos', 'duração observada das pausas do retry expressa em nanossegundos', 'tempo medido nas funções de espera em vez do tempo solicitado', 'nanossegundos medidos nos callbacks de espera excluindo as chamadas da operação')}},
    'udp_sent_datagrams': {
        'train': {
            'en': ('successful sendto calls counting empty datagrams as messages', 'number of UDP payload submissions rather than their byte volume', 'UDP messages accepted by the sending socket', 'count of outgoing datagram send events including zero-length payloads'),
            'pt': ('chamadas sendto bem-sucedidas contando datagramas vazios como mensagens', 'número de submissões de conteúdos UDP em vez do volume de bytes', 'mensagens UDP aceitas pelo socket emissor', 'contagem de eventos de envio de datagramas incluindo conteúdos vazios')},
        'validation': {
            'en': ('one counted message per completed UDP sendto', 'how many datagram transmissions the sender submitted successfully', 'accepted datagram sends with no dependence on payload length', 'outgoing UDP message count including sends of empty content'),
            'pt': ('uma mensagem contada por sendto UDP concluído', 'quantos envios de datagramas o emissor submeteu com sucesso', 'envios de datagramas aceitos sem depender do comprimento do conteúdo', 'contagem de mensagens UDP de saída incluindo envios de conteúdo vazio')}},
    'udp_sent_payload_bytes': {
        'train': {
            'en': ('payload bytes passed to successful UDP sendto calls without headers', 'sum of outgoing datagram content lengths in bytes', 'sent user-content volume rather than UDP message count', 'byte count of accepted UDP send payloads excluding protocol framing'),
            'pt': ('bytes de conteúdo passados às chamadas sendto UDP bem-sucedidas sem cabeçalhos', 'soma dos comprimentos dos conteúdos de datagramas enviados em bytes', 'volume de conteúdo enviado em vez da contagem de mensagens UDP', 'contagem de bytes dos conteúdos UDP aceitos para envio sem estruturas do protocolo')},
        'validation': {
            'en': ('total length in bytes of content submitted by the sender', 'how much user data the completed UDP sends carried in bytes', 'sum of successfully submitted UDP payload sizes excluding UDP and IP headers', 'outgoing payload volume where an empty datagram contributes zero bytes'),
            'pt': ('comprimento total em bytes do conteúdo submetido pelo emissor', 'quantos bytes de dados do usuário os envios UDP concluídos continham', 'soma dos tamanhos dos conteúdos UDP submetidos com sucesso sem cabeçalhos UDP e IP', 'volume do conteúdo enviado em que um datagrama vazio contribui zero bytes')}},
    'git_index_edits': {
        'train': {
            'en': ('staged path differences between HEAD and the Git index', 'paths with staged additions modifications or deletions', 'tracked changes prepared in the index rather than local worktree edits', 'HEAD-to-index changed-path count excluding untracked and ignored paths'),
            'pt': ('diferenças de caminhos preparadas entre HEAD e o índice Git', 'caminhos com adições modificações ou exclusões preparadas', 'alterações rastreadas preparadas no índice em vez de alterações locais', 'contagem de caminhos alterados entre HEAD e índice sem não rastreados ou ignorados')},
        'validation': {
            'en': ('distinct paths altered in the staging area relative to HEAD', 'count of index-side changes including staged removals', 'prepared changes represented by the X status column excluding untracked and ignored entries', 'number of staged file changes with each path counted once'),
            'pt': ('caminhos distintos alterados na área de preparação em relação ao HEAD', 'contagem de alterações do lado do índice incluindo exclusões preparadas', 'alterações preparadas representadas pela coluna X sem entradas não rastreadas ou ignoradas', 'número de alterações de arquivos preparadas contando cada caminho uma vez')}},
    'git_worktree_edits': {
        'train': {
            'en': ('tracked changes on disk relative to the current Git index', 'unstaged modified or deleted tracked paths', 'local worktree differences rather than prepared HEAD-to-index changes', 'index-to-disk changed-path count excluding untracked and ignored paths'),
            'pt': ('alterações rastreadas no disco em relação ao índice Git atual', 'caminhos rastreados modificados ou excluídos sem preparação', 'diferenças locais do diretório de trabalho em vez de alterações preparadas', 'contagem de caminhos alterados entre índice e disco sem não rastreados ou ignorados')},
        'validation': {
            'en': ('distinct tracked paths changed locally compared with their index state', 'count of worktree-side edits including local removals', 'unprepared changes represented by the Y status column excluding untracked and ignored entries', 'number of tracked disk changes without counting new untracked files'),
            'pt': ('caminhos rastreados distintos alterados localmente em comparação com o índice', 'contagem de alterações do diretório de trabalho incluindo exclusões locais', 'alterações não preparadas representadas pela coluna Y sem entradas não rastreadas ou ignoradas', 'número de alterações rastreadas no disco sem contar arquivos novos não rastreados')}},
}

FRAMES = {
    'train': {
        'en': ('I need the recorded {}.', 'Select the entry supplying the explicit {}.', 'Locate the field for {}; do not compute it.', 'Retrieve {} as a stored observation.'),
        'pt': ('Preciso do registro de {}.', 'Selecione a entrada que fornece explicitamente {}.', 'Localize o campo de {}; não calcule esse valor.', 'Recupere {} como observação armazenada.')},
    'validation': {
        'en': ('Where can I read {} directly?', 'Return the report containing {}.', 'Find the observation that states {}.', 'Show me the written {}.'),
        'pt': ('Onde posso ler diretamente {}?', 'Retorne o relatório que contém {}.', 'Ache a observação que informa {}.', 'Mostre o registro escrito de {}.')},
}
UNKNOWN = {
    'train': {
        'derived_or_multifield_goal': {'en': ('Compute an unrecorded ratio involving {}.', 'Estimate a missing quantity from {}.'), 'pt': ('Calcule uma razão não registrada envolvendo {}.', 'Estime uma grandeza ausente a partir de {}.')},
        'diagnosis_goal': {'en': ('Explain the mechanism that produced {}.', 'Identify the root cause behind {}.'), 'pt': ('Explique o mecanismo que produziu {}.', 'Identifique a causa raiz por trás de {}.')},
        'broader_usefulness_goal': {'en': ('Choose the full investigation context using {}.', 'Decide which evidence resolves the overall problem from {}.'), 'pt': ('Escolha o contexto completo da investigação usando {}.', 'Decida quais evidências resolvem o problema geral a partir de {}.')}},
    'validation': {
        'derived_or_multifield_goal': {'en': ('Work out an additional result absent from the record using {}.', 'Infer a second measurement that is not supplied from {}.'), 'pt': ('Obtenha um resultado adicional ausente do registro usando {}.', 'Infira outra medição não fornecida a partir de {}.')},
        'diagnosis_goal': {'en': ('What underlying process accounts for {}?', 'Determine why {} occurred.'), 'pt': ('Que processo subjacente explica {}?', 'Determine por que ocorreu {}.')},
        'broader_usefulness_goal': {'en': ('Determine all evidence needed to finish the wider task from {}.', 'Judge the usefulness of {} for the complete analysis.'), 'pt': ('Determine todas as evidências necessárias para concluir a tarefa ampla a partir de {}.', 'Julgue a utilidade de {} para a análise completa.')}},
}


def designs():
    original = load(DEVELOPMENT/'supervision-design-v3/protocol.json')
    result = {}
    for split in REQUESTS:
        d = copy.deepcopy(original)
        d['pairs'] = PAIRS
        d['query_frames'] = {split:FRAMES[split]}
        d['semantic_UNKNOWN_frames'] = {split:UNKNOWN[split]}
        for role,aliases in ALIASES.items():
            d['roles'][role][2] = list(aliases[split]['en'])
            d['roles'][role][3] = list(aliases[split]['pt'])
        result[split] = d
    return result


def validate_wording(recipes):
    assert len(ALIASES) == 8 and {r for pair in PAIRS.values() for r in pair} == set(ALIASES)
    for role in ALIASES:
        for language,position in [('en',2),('pt',3)]:
            a,b = (recipes[s]['roles'][role][position] for s in REQUESTS)
            assert len(a) == len(set(a)) == len(b) == len(set(b)) == 4
            assert not set(a) & set(b)
    for language in ('en','pt'):
        assert not set(FRAMES['train'][language]) & set(FRAMES['validation'][language])
        for kind in UNKNOWN['train']:
            assert not set(UNKNOWN['train'][kind][language]) & set(UNKNOWN['validation'][kind][language])


def run():
    if OUT.exists():
        raise ValueError('New immutable data-pilot destination required')
    recipes = designs()
    validate_wording(recipes)
    raw_audits = {s:audit_raw(DEVELOPMENT/s) for s in REQUESTS}
    source_names = ['research/wording_development_pilot.py','research/tool_relation_state_supervision.py',
                    'research/audit_tool_relation_state_supervision.py','research/measurement_projection.py',
                    'research/detached_varied_study.py','research/audit_tool_relation_confirmation.py',
                    'research/audit_tool_relation_states.py','tests/test_wording_development_pilot.py']
    capture_names = ['supervision-design-v3/protocol.json']+[f'{s}/{n}' for s in REQUESTS for n in ('protocol.json','raw.json','completion.json')]
    upstream = load(DEVELOPMENT.parent/'semantic-next/upstream/artifacts.json')
    tokenizer_files = {k:v for k,v in upstream['files'].items() if k not in ('model.safetensors','README.md')}
    snapshot = Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/upstream['revision']
    assert all(sha(snapshot/n) == v for n,v in tokenizer_files.items())
    p = dict(schema='known-report-held-goal-wording-development-pilot/0.1',frozen_at_utc=now(),
             sources={n:sha(ROOT/n) for n in source_names},capture_files={n:sha(DEVELOPMENT/n) for n in capture_names},
             requests=REQUESTS,recipes=recipes,paired_fields=PAIRS,
             reused_capture_independent_audits=raw_audits,
             goal_wording='Four independent whole authored phrase families per target field/language/split. No suffix-only expansion; all eight target aliases and question/UNKNOWN frames disjoint by split.',
             report_wording='Known original record-caption vocabulary; no report-paraphrase novelty claim. Remaining10field aliases known in UNKNOWN cases.',
             scope='Eight known relevance fields/four hard within-tool pairs,18known fields in semantic UNKNOWN. Original64/32author fixtures and actual values reused; no final capture/rows or tools reexecuted. Exposed development pilot, not confirmation or full18field gate.',
             tokenizer=dict(revision=upstream['revision'],files=tokenizer_files,window=512),
             expected_rows=dict(train=11136,validation=5568),model_forwards=0,API_calls=0,
             quality_approved=False,default_changed=False,P2_admission=False)
    p['sha256'] = digest(p)
    OUT.mkdir()
    for name,value in p['sources'].items():
        target = OUT/'sources'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        assert sha(target) == value
    save(OUT/'protocol.json',p)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    coverage,split_hashes = {},{}
    for split in REQUESTS:
        raw = load(DEVELOPMENT/split/'raw.json')
        coverage[split] = write_rows(OUT,split,build_rows(split,raw,recipes[split],requests=REQUESTS),tokenizer)
        projected,identities = set(),set()
        for row in rows(OUT/f'{split}.jsonl.gz'):
            inspect_row(row,recipes[split],raw,requests=REQUESTS)
            assert row['id'] not in identities
            identities.add(row['id'])
            if row['projected_input_hash']:projected.add(row['projected_input_hash'])
        assert len(identities) == p['expected_rows'][split]
        split_hashes[split] = projected
    assert not split_hashes['train'] & split_hashes['validation']
    assert all(sha(DEVELOPMENT/n) == v for n,v in p['capture_files'].items())
    result = dict(status='PASS',protocol_sha256=p['sha256'],coverage=coverage,split_projected_overlap=0,
                  independent_row_inspection=True,tokenizer_whole_pairs=True,cuts=0,
                  finished_at_utc=now(),model_forwards=0,API_calls=0,quality_approved=False,scope=p['scope'])
    save(OUT/'audit.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(),indent=2,allow_nan=False))
