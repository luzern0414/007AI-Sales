export async function exitSession(flush, revoke, leave) {
  await flush();
  await revoke();
  leave();
}
