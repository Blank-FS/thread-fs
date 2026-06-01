export class ThreadFSServerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ThreadFSServerError";
  }
}
