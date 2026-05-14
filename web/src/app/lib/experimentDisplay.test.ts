import { getExperimentArenaSize } from "./experimentDisplay";

describe("experimentDisplay", () => {
  it("keeps dense first trials large but within the viewport", () => {
    expect(getExperimentArenaSize(1440, 900, 58)).toBe(750);
    expect(getExperimentArenaSize(390, 844, 58)).toBe(294);
  });

  it("uses the smaller default cap for ordinary set-cover batches", () => {
    expect(getExperimentArenaSize(1440, 900, 8)).toBe(640);
    expect(getExperimentArenaSize(390, 844, 8)).toBe(280);
  });
});
