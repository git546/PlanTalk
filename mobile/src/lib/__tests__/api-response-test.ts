import { fetchReply, fetchSpeciesReference } from '@/lib/api';

jest.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: async () => ({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}));

const messages = [{ role: 'user' as const, content: '안녕' }];

function mockResponse(
  body: string,
  { status = 200, contentType = 'application/json', redirected = false } = {},
) {
  const json = jest.fn(async () => JSON.parse(body));
  jest.spyOn(globalThis, 'fetch').mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    redirected,
    headers: { get: () => contentType },
    json,
  } as unknown as Response);
  return json;
}

afterEach(() => jest.restoreAllMocks());

test.each([
  [502, '서버 연결에 문제가 생겼어요.'],
  [504, '서버 응답 시간이 초과됐어요.'],
])('handles an HTML gateway error (%i) before parsing the body', async (status, message) => {
  const json = mockResponse('<!DOCTYPE html><title>Gateway error</title>', {
    status, contentType: 'text/html; charset=utf-8',
  });

  await expect(fetchReply(messages)).rejects.toThrow(message);
  expect(json).not.toHaveBeenCalled();
});

test('handles a redirect to an HTML access page even when its final status is 200', async () => {
  mockResponse('<!DOCTYPE html><title>Preview login</title>', {
    contentType: 'text/html', redirected: true,
  });

  await expect(fetchReply(messages)).rejects.toThrow('접속 권한을 확인할 수 없어요.');
});

test('handles a malformed body even when the server labels it JSON', async () => {
  mockResponse('<!DOCTYPE html>');

  await expect(fetchSpeciesReference('몬스테라')).rejects.toThrow('서버 응답을 읽을 수 없어요.');
});

test('preserves backend error details and accepts valid JSON chat replies', async () => {
  mockResponse('{"detail":"AI 응답 시간이 초과됐어요."}', {
    status: 504, contentType: 'application/json; charset=utf-8',
  });
  await expect(fetchReply(messages)).rejects.toThrow('AI 응답 시간이 초과됐어요.');

  mockResponse('{"reply":"안녕!"}');
  await expect(fetchReply(messages)).resolves.toBe('안녕!');
  expect(globalThis.fetch).toHaveBeenLastCalledWith(
    expect.stringContaining('/api/chat'),
    expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
  );
});
