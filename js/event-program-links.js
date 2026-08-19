const programmeKeysByCity = {
  Avezzano: "avezzano",
  Terni: "terni",
  Pisa: "pisa",
  Bari: "bari",
  "Paris / Palaiseau": "paris",
  Napoli: "napoli",
  Naples: "napoli",
  Pavia: "pavia",
  Manchester: "manchester",
  Roma: "roma",
  Rome: "roma",
  Palermo: "palermo",
  Bologna: "bologna",
  Padova: "padova",
  Padoue: "padova",
  Cagliari: "cagliari",
  Turin: "torino",
  Torino: "torino",
  Alessandria: "alessandria"
};

const programmeLabels = {
  en: "View programme",
  it: "Vedi il programma",
  fr: "Voir le programme"
};

document.querySelectorAll(".event-detail-card").forEach((card) => {
  const city = card.querySelector("h3")?.textContent.trim();
  const key = programmeKeysByCity[city];
  if (!key || card.querySelector(".event-program-link")) return;

  const link = document.createElement("a");
  link.className = "button button-secondary event-program-link";
  link.href = `programmi-ern-2026.html?evento=${key}`;
  link.textContent = programmeLabels[document.documentElement.lang] || programmeLabels.en;
  card.append(link);
});
