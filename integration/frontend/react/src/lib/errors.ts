export class ThreadFSApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ThreadFSApiError";
    this.status = status;
    this.body = body;
  }
}
