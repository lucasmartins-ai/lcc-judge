"""Fresh authored wording and reserved pair coverage; primitives/tools stay known.

Two semantic bases per language/axis, four explicit surface renderings. These
are lexical confirmation, not new tool meanings, human ground truth or P2.
"""

from itertools import combinations

from research.tool_relation_state_contracts import ROLES as KNOWN, PAIRS as SEEN

# English/Portuguese intent bases, then separately authored report-caption bases.
BASES = {
    'retry_attempts': (
        ('count of operation invocations including the original try', 'number of executions made before the retrying call terminates'),
        ('contagem de invocações da operação incluindo a tentativa original', 'número de execuções feitas antes do término da chamada de retry'),
        ('Executed attempts tallied from the first invocation onward', 'Recorded Retrying executions until return or exhaustion'),
        ('Tentativas executadas contadas desde a invocação inicial', 'Execuções do Retrying registradas até retorno ou esgotamento')),
    'retry_failures': (
        ('number of unsuccessful operation calls, including terminal exhaustion failures', 'tally of exception outcomes recorded across the retry attempts'),
        ('número de chamadas sem sucesso incluindo falhas no esgotamento terminal', 'contagem de resultados com exceção nas tentativas de retry'),
        ('Operation attempts whose recorded outcome was an exception', 'Failures counted before the Retrying invocation ended'),
        ('Tentativas da operação cujo resultado registrado foi uma exceção', 'Falhas contadas antes do término da invocação do Retrying')),
    'retry_sleep_calls': (
        ('count of sleeper function executions between retry calls', 'number of inter-attempt waiting callbacks actually invoked'),
        ('contagem de execuções da função de espera entre chamadas de retry', 'número de callbacks de espera entre tentativas realmente invocados'),
        ('Executed sleeper callbacks counted as events', 'Waiting-function invocations recorded between operation attempts'),
        ('Callbacks da função de espera executados e contados como eventos', 'Invocações de espera registradas entre tentativas da operação')),
    'retry_scheduled_sleep_ns': (
        ('nominal delay requested for all retry waits in nanoseconds', 'nanosecond sum of policy-assigned waiting intervals'),
        ('atraso nominal solicitado para todas as esperas de retry em nanossegundos', 'soma em nanossegundos dos intervalos de espera atribuídos pela política'),
        ('Requested wait_fixed delays added in nanoseconds', 'Scheduled retry waiting budget expressed as nanoseconds'),
        ('Atrasos solicitados por wait_fixed somados em nanossegundos', 'Tempo de espera programado do retry expresso em nanossegundos')),
    'retry_actual_sleep_ns': (
        ('nanoseconds measured around the executed sleeper callbacks', 'total observed waiting-function duration excluding operation execution'),
        ('nanossegundos medidos ao redor dos callbacks de espera executados', 'duração total observada da função de espera sem a execução da operação'),
        ('Monotonic sleeper-entry to sleeper-exit intervals summed in nanoseconds', 'Elapsed nanoseconds inside callbacks responsible for waiting'),
        ('Intervalos monotônicos entre entrada e saída da espera somados em nanossegundos', 'Nanossegundos transcorridos dentro dos callbacks responsáveis pela espera')),
    'retry_elapsed_ns': (
        ('monotonic nanoseconds covering the entire retrying invocation', 'complete retry-call duration including failed calls and waiting'),
        ('nanossegundos monotônicos que abrangem toda a invocação de retry', 'duração completa da chamada de retry incluindo falhas e esperas'),
        ('Nanoseconds from entering Retrying until return or exhaustion', 'Overall retry execution interval including operations and sleepers'),
        ('Nanossegundos da entrada no Retrying até retorno ou esgotamento', 'Intervalo de execução total do retry incluindo operações e esperas')),
    'udp_sent_datagrams': (
        ('number of successful datagram sendto submissions including zero-length ones', 'count of UDP messages passed to the sending socket'),
        ('número de submissões sendto bem-sucedidas incluindo datagramas vazios', 'contagem de mensagens UDP passadas ao socket emissor'),
        ('Successful UDP sending calls tallied by message', 'Transmitted datagram events, counting empty content as one'),
        ('Chamadas de envio UDP bem-sucedidas contadas por mensagem', 'Eventos de transmissão de datagramas contando conteúdo vazio como um')),
    'udp_received_datagrams': (
        ('count of datagram reads completed by recvfrom including empty messages', 'number of UDP messages actually read by the bounded receiver'),
        ('contagem de leituras recvfrom concluídas incluindo mensagens vazias', 'número de mensagens UDP realmente lidas pelo receptor limitado'),
        ('Completed receiver calls tallied as datagram events', 'Observed UDP message reads with zero-length reads counted'),
        ('Chamadas concluídas no receptor contadas como eventos de datagrama', 'Leituras observadas de mensagens UDP incluindo conteúdos de tamanho zero')),
    'udp_sent_payload_bytes': (
        ('byte total of user content submitted in outgoing datagrams', 'sum of successful sendto payload lengths without protocol headers'),
        ('total de bytes do conteúdo submetido nos datagramas de saída', 'soma dos comprimentos enviados por sendto sem cabeçalhos de protocolo'),
        ('UDP sending payload sizes accumulated in bytes', 'Outgoing content byte count excluding UDP and IP framing'),
        ('Tamanhos dos conteúdos enviados por UDP acumulados em bytes', 'Contagem de bytes do conteúdo de saída sem estruturas UDP e IP')),
    'udp_received_payload_bytes': (
        ('byte total of user content returned by datagram reads', 'sum of recvfrom payload lengths without protocol headers'),
        ('total de bytes do conteúdo retornado pelas leituras de datagramas', 'soma dos comprimentos retornados por recvfrom sem cabeçalhos de protocolo'),
        ('UDP read payload sizes accumulated in bytes', 'Receiver content byte count excluding UDP and IP framing'),
        ('Tamanhos dos conteúdos lidos por UDP acumulados em bytes', 'Contagem de bytes do conteúdo no receptor sem estruturas UDP e IP')),
    'git_index_files': (
        ('number of paths currently stored in the Git index, including missing disk files', 'count of cached Git names rather than a filesystem listing'),
        ('número de caminhos atualmente no índice Git incluindo arquivos ausentes no disco', 'contagem de nomes no cache do Git em vez de uma listagem do disco'),
        ('Current index names counted from the cached-path listing', 'Git index membership total even when an indexed file is absent locally'),
        ('Nomes atuais no índice contados na listagem de caminhos em cache', 'Total de entradas do índice Git mesmo quando um arquivo indexado falta localmente')),
    'git_untracked_files': (
        ('number of nonignored disk paths not entered in the Git index', 'count of unversioned files left after applying Git ignore rules'),
        ('número de caminhos no disco não ignorados e ausentes do índice Git', 'contagem de arquivos não versionados após aplicar as regras de ignore do Git'),
        ('Paths outside index membership and outside ignore matches', 'Untracked file entries retained by the exclude-standard filter'),
        ('Caminhos fora do índice e fora das correspondências de ignore', 'Entradas não rastreadas mantidas pelo filtro exclude-standard')),
    'git_ignored_files': (
        ('number of unindexed files hidden by Git ignore matches', 'count of locally present untracked paths excluded by repository ignore rules'),
        ('número de arquivos fora do índice ocultados pelas regras de ignore do Git', 'contagem de caminhos locais não rastreados excluídos pelas regras do repositório'),
        ('Ignored untracked entries from the exclude-standard ignored listing', 'Local files outside the index selected by ignore patterns'),
        ('Entradas não rastreadas ignoradas na listagem exclude-standard ignored', 'Arquivos locais fora do índice selecionados pelos padrões de ignore')),
    'git_index_edits': (
        ('number of paths changed in the index relative to HEAD, staged removals included', 'count of distinct paths with a non-space X flag in Git status'),
        ('número de caminhos alterados no índice em relação ao HEAD incluindo exclusões preparadas', 'contagem de caminhos distintos com marca X não vazia no status Git'),
        ('HEAD-to-index path differences counted once including additions and deletions', 'Staged status-column entries tallied without requiring present index membership'),
        ('Diferenças por caminho entre HEAD e índice contadas uma vez incluindo adições e exclusões', 'Entradas da coluna preparada contadas mesmo sem presença atual no índice')),
    'git_worktree_edits': (
        ('number of tracked paths locally changed relative to the Git index', 'count of distinct paths with a non-space Y flag, local deletions included'),
        ('número de caminhos rastreados alterados localmente em relação ao índice Git', 'contagem de caminhos distintos com marca Y não vazia incluindo exclusões locais'),
        ('Index-to-disk changes represented by worktree status flags', 'Unstaged modified or removed paths counted once per status entry'),
        ('Alterações entre índice e disco representadas por marcas do diretório de trabalho', 'Caminhos modificados ou removidos sem preparação contados uma vez por entrada')),
    'git_clean_tracked_files': (
        ('number of index paths lacking both staged and local changes', 'count of tracked names omitted from the changed-status path set'),
        ('número de caminhos no índice sem alterações preparadas nem locais', 'contagem de nomes rastreados ausentes do conjunto de caminhos alterados no status'),
        ('Indexed names with no X or Y change recorded', 'Clean index members after subtracting changed tracked paths'),
        ('Nomes indexados sem alteração X ou Y registrada', 'Entradas limpas do índice após excluir caminhos rastreados alterados')),
    'git_tracked_fs_bytes': (
        ('byte sum of existing on-disk files whose names are in the current Git index', 'current indexed file content volume with absent files excluded'),
        ('soma de bytes dos arquivos existentes no disco com nomes no índice Git atual', 'volume atual de conteúdo dos arquivos indexados excluindo os ausentes'),
        ('Filesystem lengths of present indexed files accumulated in bytes', 'Local byte total for tracked content that still exists'),
        ('Comprimentos no disco dos arquivos indexados presentes acumulados em bytes', 'Total de bytes locais dos conteúdos rastreados ainda existentes')),
    'git_untracked_fs_bytes': (
        ('byte sum of nonignored on-disk files absent from the Git index', 'local unversioned content volume after removing ignored paths'),
        ('soma de bytes dos arquivos não ignorados no disco e ausentes do índice Git', 'volume de conteúdo local não versionado após excluir caminhos ignorados'),
        ('Filesystem lengths of untracked nonignored files accumulated in bytes', 'Local byte total outside index membership and ignore matches'),
        ('Comprimentos no disco dos arquivos não rastreados e não ignorados acumulados em bytes', 'Total de bytes locais fora do índice e das correspondências de ignore')),
}

ROLES = {}; PT_CAPTIONS = {}
for name, (en, pt, captions_en, captions_pt) in BASES.items():
    en = (*en, 'observed value for '+en[0], 'recorded value for '+en[1])
    pt = (*pt, 'valor observado de '+pt[0], 'valor registrado de '+pt[1])
    captions_en = (*captions_en, 'Observation: '+captions_en[0], 'Measurement: '+captions_en[1])
    captions_pt = (*captions_pt, 'Observação: '+captions_pt[0], 'Medição: '+captions_pt[1])
    if name.startswith('udp_received_'):
        en = tuple(v+' within the recorded receiver read budget' for v in en)
        captions_en = tuple(v+' within the recorded receiver read budget' for v in captions_en)
        pt = tuple(v+' dentro do limite de leitura registrado do receptor' for v in pt)
        captions_pt = tuple(v+' dentro do limite de leitura registrado do receptor' for v in captions_pt)
    ROLES[name] = (*KNOWN[name][:2], en, pt, captions_en)
    PT_CAPTIONS[name] = captions_pt

known_pairs = {tuple(sorted(v)) for v in SEEN.values()}
PAIRS = {f'{"seen_control" if (a,b) in known_pairs else "primary"}:{a}:{b}': (a,b)
         for a,b in combinations(sorted(ROLES),2)}

DIRECT_FRAMES = {'final': {
    'en': ('Identify the log entry that records {}.', 'Retrieve the reported measurement for {}.',
           'Which stored field names {}?', 'Point to the entry supplying {}.'),
    'pt': ('Identifique a entrada que registra {}.', 'Recupere a medição informada de {}.',
           'Qual campo armazenado indica {}?', 'Aponte a entrada que fornece {}.'),
}}
UNKNOWN_FRAMES = {'final': {
    'derived_or_multifield_goal': {
        'en': ('Calculate a quantity that is not explicitly present, using {}.', 'Combine {} with a missing field to obtain a new result.'),
        'pt': ('Calcule uma grandeza não escrita no registro usando {}.', 'Combine {} com um campo ausente para obter um novo resultado.')},
    'diagnosis_goal': {
        'en': ('Establish the explanation behind the behavior using {}.', 'Account for the underlying problem from the measurement of {}.'),
        'pt': ('Estabeleça a explicação do comportamento usando {}.', 'Explique o problema subjacente a partir da medição de {}.')},
    'broader_usefulness_goal': {
        'en': ('Decide which evidence the entire investigation needs using {}.', 'Select all context necessary to solve the wider task from {}.'),
        'pt': ('Decida quais evidências toda a investigação exige usando {}.', 'Selecione todo o contexto necessário para resolver a tarefa ampla a partir de {}.')},
}}
