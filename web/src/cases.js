// Guided case files. Every number in the text is read from the pipeline's files
// through the helper `h`; nothing here is typed in by hand.
export const CASES = [
  {
    id: "fingerprint",
    title: "One cause, opposite trends",
    question: "Is the whole atmosphere warming?",
    steps: [
      { set: { dataset: "airs", variable: "t", period: "overlap", mask: "none", place: { region: "global" }, hpa: 925, witness: false },
        say: (h) => `Start near the ground. Averaged over the whole globe, the air about ${h.km(925)} km up has ${h.verb(925)} by ${h.rate(925)} since ${h.since()}. Label: ${h.label(925)}.` },
      { set: { hpa: 10 },
        say: (h) => `Now climb to about ${h.km(10)} km, far above the weather. Same planet, same years: the air there has ${h.verb(10)} by ${h.rate(10)}. Label: ${h.label(10)}.` },
      { set: { hpa: 50 },
        say: (h) => `In between, around ${h.km(50)} km, our best estimate is ${h.rate(50)}. Label: ${h.label(50)}. That does not mean nothing changed. It means the change is too small to tell apart from chance.` },
      { set: { hpa: 10, witness: true },
        say: (h) => (h.hasOther()
          ? `The dashed orange line is a second, independent dataset (${h.otherName()}). At ${h.km(925)} km it shows ${h.other(925)}, and at ${h.km(10)} km ${h.other(10)}. `
          : "")
          + `Physicists predicted this pattern in 1967 as the mark of rising carbon dioxide: warming below, cooling above. A 2023 study found it in satellite records (Santer and others, PNAS 2023).` },
    ],
  },
  {
    id: "volcano",
    title: "A volcano in the record",
    question: "Did the 2022 eruption cause the cooling?",
    steps: [
      { set: { dataset: "airs", variable: "t", period: "overlap", mask: "none", place: { region: "south_mid" }, hpa: 10, witness: false },
        say: (h) => `In January 2022 the Hunga volcano in the Pacific threw a record amount of water vapor into the calm layer. Find the shaded band for 2022 and 2023 in the history chart below. About ${h.km(10)} km up, the air ran colder than normal for many months.` },
      { set: { mask: "no_hunga" },
        say: (h) => `Now those two years are left out. The trend goes from ${h.rate(10, "none")} to ${h.rate(10, "no_hunga")}. Label: ${h.label(10, "no_hunga")}.` },
      { set: { mask: "none" },
        say: (h) => (h.share(10, "none", "no_hunga") < 0.5
          ? `So the volcano left a dent, but it does not explain the cooling: the trend barely moves without it. `
          : `Here the volcano matters: the trend changes a lot without those months. `)
          + `Lapse runs this check on every trend. When leaving out volcano months changes a trend by more than half, the label becomes "Disputed".` },
    ],
  },
  {
    id: "jump",
    title: "When the data source jumps",
    question: "Can a trend be fake?",
    steps: [
      { set: { dataset: "merra2", variable: "t", period: "full", mask: "none", place: { region: "global" }, hpa: 1, witness: false },
        say: (h) => `This is ${h.years()} years from a weather model corrected by real measurements, about ${h.km(1)} km up. Find the two blue bands in the history chart. At those moments the model started using new satellites, and the line jumps by about ${h.step(1)} °C.` },
      { set: { period: "overlap", hpa: 3 },
        say: (h) => `Now look only at the years since ${h.since()}, about ${h.km(3)} km up. The record jumps by ${h.step(3)} °C when the data source changed in 2004. The whole trend adds up to ${h.total(3)}. ${h.bigger(3) ? "The jump is bigger than the trend" : "The jump explains much of the trend"}, so the label is ${h.label(3)}.` },
      { set: { witness: true },
        say: (h) => (h.hasOther()
          ? `The dashed line is ${h.otherName()}, one instrument that did not change. It shows ${h.other(3)} here, so some cooling is probably real, but this model cannot tell us how much. `
          : "")
          + `The lesson: when the measuring tool changes, check a second source before trusting a trend.` },
    ],
  },
];
