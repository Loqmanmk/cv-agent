export type Header = {
  name: string;
  headline: string;
  target_line: string;
  phone: string;
  email: string;
  linkedin: string;
  github: string;
  location: string;
};

export type Experience = {
  title: string;
  company: string;
  city: string;
  start: string;
  end: string;
  bullets: string[];
};

export type Project = {
  title: string;
  subtitle: string;
  bullets: string[];
};

export type Education = {
  degree: string;
  school: string;
  city: string;
  start: string;
  end: string;
  note: string;
};

export type SkillGroup = {
  category: string;
  items: string[];
};

export type Certification = {
  name: string;
  issuer: string;
  status: string;
};

export type Language = {
  name: string;
  level: string;
};

export type Cv = {
  header: Header;
  profile: string;
  experiences: Experience[];
  projects: Project[];
  education: Education[];
  skills: SkillGroup[];
  certifications: Certification[];
  languages: Language[];
  interests: string[];
};

/** group: the skill group of the CV it belongs in, or null for the group of added skills. */
export type MissingSkill = { name: string; required: boolean; group: string | null };

/** How the tailored CV matches the offer. Computed by the server, not written by the AI. */
/** How well the CV the user sent fits the offer, from the skills the offer names. */
export type MatchScore = {
  /** 0 to 100, or null when the offer names no skills. */
  value: number | null;
  requiredMatched: number;
  requiredTotal: number;
  niceMatched: number;
  niceTotal: number;
};

export type MatchReport = {
  matchedSkills: string[];
  missingSkills: MissingSkill[];
  changes: string[];
  score: MatchScore;
};

export type CoverLetter = {
  sender: { name: string; address: string; email: string; phone: string };
  recipient: { contact: string; company: string; address: string };
  place_date: string;
  subject: string;
  greeting: string;
  paragraphs: string[];
  signature: string;
};
