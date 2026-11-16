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

export type MissingSkill = { name: string; required: boolean };

/** How the tailored CV matches the offer. Computed by the server, not written by the AI. */
export type MatchReport = {
  matchedSkills: string[];
  missingSkills: MissingSkill[];
  changes: string[];
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
