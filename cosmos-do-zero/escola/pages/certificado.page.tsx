import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Lead, Meta } from '../src/components/Frame';
import { levels } from '../src/lib/school';
import { CLASSROOM, isPages } from '../src/lib/student';
export default function Certificate() {
  const id = useRouter().query.id,
    [data, set] = useState<{ name: string; level: number; issued: string } | null>(null),
    [msg, setMsg] = useState('Informe o identificador do certificado.');
  useEffect(() => {
    if (typeof id !== 'string') return;
    const link =
      (isPages() ? CLASSROOM : '') + '/api/school/?op=certificate-view&id=' + encodeURIComponent(id);
    fetch(link)
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw Error(j.message);
        set(j);
      })
      .catch((e) => setMsg(e.message));
  }, [id]);
  return (
    <>
      <Meta title="Certificado" />
      <Lead tag="Escola Cosmos" title="Certificado de conclusão" />
      <div className="wrap reading block">
        {data ? (
          <>
            <h2>{data.name}</h2>
            <p>
              Concluiu os exercícios e foi aprovado na avaliação do nível {data.level},{' '}
              {levels[data.level - 1]?.name}.
            </p>
            <p>
              Emitido em {new Date(data.issued).toLocaleDateString('pt-BR')} · {id}
            </p>
            <button className="btn dark" onClick={() => window.print()}>
              Imprimir certificado
            </button>
          </>
        ) : (
          <p>{msg}</p>
        )}
      </div>
    </>
  );
}
