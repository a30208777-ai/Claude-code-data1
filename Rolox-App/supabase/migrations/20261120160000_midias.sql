-- Sons e vídeos dos criadores (usados nos jogos). Bucket "midias":
--  * leitura pública (os jogadores tocam direto do bucket);
--  * envio só logado, só na própria pasta <user_id>/, até 20 MB, só áudio/vídeo.
-- O site ainda confere o começo do arquivo (assinatura) antes de enviar.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('midias', 'midias', true, 20971520,
        array['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/webm', 'video/mp4', 'video/webm'])
on conflict (id) do nothing;

create policy "midias: criador envia na própria pasta" on storage.objects for insert to authenticated
  with check (bucket_id = 'midias' and (storage.foldername(name))[1] = auth.uid()::text);
