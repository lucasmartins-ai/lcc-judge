"""Expanded authored direct-record vocabulary and connected development coverage.

Known eighteen primitives/tools; no production/domain novelty or P2. Existing
scored aliases are exposed development vocabulary. Both report languages are
explicit. Retry termination is not assumed successful; index changes include
staged deletions. Broad/derived/diagnostic goals remain semantic UNKNOWN.
"""

from itertools import combinations,product
import random

from research.tool_relation_contracts import ROLES as PREVIOUS_ROLES,REFERENCES

ROLES=dict(PREVIOUS_ROLES)


def _replace(role,position,index,value):
    record=list(ROLES[role]);items=list(record[position]);items[index]=value;record[position]=tuple(items)
    ROLES[role]=tuple(record)


_replace('retry_attempts',2,2,'number of attempts from initial invocation to termination')
_replace('retry_attempts',3,2,'número de tentativas da invocação inicial até o término')
_replace('retry_attempts',4,0,'Retrying attempt_number observed at termination')
_replace('retry_failures',4,1,'Failed operation calls before termination')
_replace('retry_elapsed_ns',2,3,'monotonic duration from retry start until termination')
_replace('retry_elapsed_ns',3,3,'duração monotônica do início do retry até o término')
_replace('git_index_edits',2,2,'paths changed between HEAD and index, including staged deletions')
_replace('git_index_edits',3,2,'caminhos alterados entre HEAD e índice, incluindo exclusões preparadas')
_replace('git_index_edits',4,3,'Git status X-column edits including staged additions and deletions, each path counted once')
_replace('git_tracked_fs_bytes',4,2,'Tracked on-disk data total excluding absent indexed paths')

PT_CAPTIONS={
    'retry_attempts':('Tentativas observadas até o término do Retrying','Chamada inicial mais todas as repetições','Total de invocações registrado no callback de retry','Eventos de tentativa incluindo a primeira execução'),
    'retry_failures':('Tentativas do Retrying que geraram exceção','Chamadas da operação que falharam até o término','Eventos do callback marcados como falha','Execuções sem sucesso incluindo a última se o limite esgotou'),
    'retry_sleep_calls':('Invocações observadas do callback de sleep','Contagem de esperas entre tentativas','Chamadas registradas à função de espera do retry','Número de callbacks de sleep executados'),
    'retry_scheduled_sleep_ns':('Atrasos programados pelo Retrying em nanossegundos','Espera nominal da política de retry em nanossegundos','Duração total de sleep solicitada por wait_fixed em nanossegundos','Soma dos intervalos solicitados ao callback de sleep em nanossegundos'),
    'retry_actual_sleep_ns':('Duração medida dos callbacks de sleep em nanossegundos','Tempo observado dentro da função de espera do retry em nanossegundos','Soma dos intervalos reais antes e depois do sleep em nanossegundos','Tempo efetivo nos callbacks de espera sem contar as chamadas da operação, em nanossegundos'),
    'retry_elapsed_ns':('Duração completa da invocação do Retrying em nanossegundos','Tempo monotônico entre início e término do retry em nanossegundos','Chamadas da operação e esperas juntas em nanossegundos','Duração total observada ao redor do laço de retry em nanossegundos'),
    'udp_sent_datagrams':('Eventos de sendto incluindo conteúdo vazio','Total de mensagens UDP enviadas','Número de datagramas transmitidos pelo socket local','Submissões de datagramas observadas no socket emissor'),
    'udp_received_datagrams':('Eventos de recvfrom incluindo conteúdo vazio','Total de mensagens UDP lidas pelo receptor','Número de datagramas observados dentro do limite de leitura','Chegadas observadas nas chamadas do socket receptor'),
    'udp_sent_payload_bytes':('Soma em bytes dos conteúdos passados a sendto','Total de bytes de conteúdo UDP enviados','Dados enviados em bytes sem cabeçalhos IP ou UDP','Volume de conteúdo submetido ao socket de datagramas em bytes'),
    'udp_received_payload_bytes':('Soma em bytes dos conteúdos retornados por recvfrom','Total de bytes UDP obtidos nas leituras do receptor','Dados lidos em bytes sem cabeçalhos IP ou UDP','Volume de conteúdo retornado pelas chamadas de recebimento em bytes'),
    'git_index_files':('Caminhos retornados por git ls-files --cached','Total de entradas de arquivo no índice Git','Caminhos no índice incluindo os que faltam no diretório de trabalho','Número de nomes de arquivo atualmente indexados pelo Git'),
    'git_untracked_files':('Caminhos retornados por git ls-files --others --exclude-standard','Total de caminhos não rastreados e não ignorados','Entradas de status Git com dois pontos de interrogação','Número de arquivos novos fora do índice Git'),
    'git_ignored_files':('Caminhos retornados por git ls-files --others --ignored --exclude-standard','Total de caminhos não rastreados que as regras de ignore excluem','Entradas de status Git com dois pontos de exclamação','Número de arquivos presentes abrangidos pelas regras de ignore'),
    'git_index_edits':('Colunas de índice não vazias no status Git','Contagem de alterações preparadas incluindo exclusões','Caminhos cujo estado difere entre HEAD e índice','Alterações na coluna X incluindo adições e exclusões, cada caminho contado uma vez'),
    'git_worktree_edits':('Colunas de diretório de trabalho não vazias no status Git','Contagem de alterações não preparadas incluindo exclusões locais','Caminhos rastreados que diferem entre índice e disco','Alterações na coluna Y do status Git, cada caminho contado uma vez'),
    'git_clean_tracked_files':('Caminhos do índice sem alteração em nenhuma coluna de status','Total de caminhos rastreados sem mudanças','Entradas de arquivo sem mudanças preparadas ou locais','Número de caminhos do índice ausentes das linhas alteradas de status'),
    'git_tracked_fs_bytes':('Tamanho em bytes dos arquivos existentes com caminhos no índice','Bytes dos conteúdos rastreados presentes no disco','Total de dados locais rastreados excluindo caminhos ausentes','Volume atual em bytes dos arquivos indexados ainda existentes'),
    'git_untracked_fs_bytes':('Tamanho em bytes dos arquivos não rastreados e não ignorados','Bytes dos conteúdos de arquivos novos fora do índice','Total de dados locais fora do índice após excluir os ignorados','Volume atual em bytes dos arquivos não rastreados pelo Git'),
}
# Clarify that the receiver is a bounded observer, not a transport-loss oracle.
_replace('udp_received_datagrams',4,2,'Number of UDP datagrams observed within the receiver read budget')
_replace('udp_received_payload_bytes',4,2,'Received payload data bytes within observed reads, excluding IP and UDP headers')

PAIRS={}
for source in ['retry','udp','git']:
    roles=sorted(role for role,value in ROLES.items() if value[0]==source)
    for a,b in combinations(roles,2):PAIRS[f'{source}:{a}:{b}']=(a,b)
for a,b in [('retry_attempts','udp_sent_datagrams'),('udp_received_datagrams','git_index_files'),('git_worktree_edits','retry_failures')]:
    a,b=sorted([a,b]);PAIRS[f'bridge:{a}:{b}']=(a,b)

DIRECT_FRAMES={
    'train':{'en':('Select the direct recorded value of {}.','Which record explicitly states {}?',
                   'Keep the field observation for {}.','Choose the line that directly reports {}.'),
             'pt':('Selecione o valor registrado diretamente de {}.','Qual registro informa explicitamente {}?',
                   'Mantenha a observação do campo de {}.','Escolha a linha que relata diretamente {}.')},
    'validation':{'en':('Provide the direct-record entry describing {}.','Locate the explicit observation of {}.'),
                  'pt':('Forneça a entrada registrada diretamente que descreve {}.','Localize a observação explícita de {}.')},
}
UNKNOWN_FRAMES={
    'train':{
        'derived_or_multifield_goal':{'en':('Use the direct record for {} to infer a missing measurement.','Find the record for {} and derive another quantity from it.'),
                                    'pt':('Use o registro direto de {} para inferir uma medição ausente.','Encontre o registro de {} e derive outra quantidade a partir dele.')},
        'diagnosis_goal':{'en':('Use the direct record for {} to diagnose why the operation behaved this way.','Find the observation of {} and explain the underlying cause.'),
                          'pt':('Use o registro direto de {} para diagnosticar por que a operação se comportou dessa forma.','Encontre a observação de {} e explique a causa subjacente.')},
        'broader_usefulness_goal':{'en':('Use the direct record for {} to decide which evidence is essential for the overall task.','Find the observation of {} and choose the context needed for the complete analysis.'),
                                  'pt':('Use o registro direto de {} para decidir quais evidências são essenciais para a tarefa geral.','Encontre a observação de {} e escolha o contexto necessário para a análise completa.')},
    },
    'validation':{
        'derived_or_multifield_goal':{'en':('Starting from the recorded value of {}, work out an additional unrecorded quantity.',),
                                    'pt':('Partindo do valor registrado de {}, obtenha outra quantidade não registrada.',)},
        'diagnosis_goal':{'en':('With the explicit observation of {}, investigate what caused the behavior.',),
                          'pt':('Com a observação explícita de {}, investigue o que causou o comportamento.',)},
        'broader_usefulness_goal':{'en':('From the field observation of {}, determine everything required for the wider objective.',),
                                  'pt':('A partir da observação do campo de {}, determine tudo que é necessário para o objetivo mais amplo.',)},
    },
}


def goal(role,language,alias,split,kind=None,template_index=0):
    if role not in ROLES or language not in ('en','pt') or type(alias) is not int or not 0<=alias<4:
        raise ValueError('Known role/language/alias required')
    if split not in DIRECT_FRAMES or type(template_index) is not int:raise ValueError('Development split and template index required')
    intent=ROLES[role][2 if language=='en' else 3][alias]
    frames=DIRECT_FRAMES[split][language] if kind is None else UNKNOWN_FRAMES[split][kind][language]
    return frames[template_index%len(frames)].format(intent)


def report_caption(role,language,alias):
    if role not in ROLES or language not in ('en','pt') or type(alias) is not int or not 0<=alias<4:
        raise ValueError('Known role/language/caption index required')
    return ROLES[role][4][alias] if language=='en' else PT_CAPTIONS[role][alias]


def wording_assignment(seed,count):
    if type(seed) is not int or not 0<=seed<2**31 or type(count) is not int or count not in (32,64):
        raise ValueError('Whole 32-way wording factorial for bounded development cohorts required')
    values=list(product(range(4),range(4),['en','pt']))*(count//32)
    random.Random(f'wording-only:{seed}').shuffle(values)
    return values
