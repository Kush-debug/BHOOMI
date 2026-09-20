import React, { useState, useEffect } from 'react';
import { MapPin, Loader2, AlertCircle } from 'lucide-react';
import api from '../../services/api';
import { useLanguage } from '../../context/LanguageContext';

export const CascadingLocationPicker = ({
  selectedState,
  selectedDistrict,
  selectedTehsil,
  selectedVillage,
  onChange,
  required = true,
  layout = "grid" // "grid" (2x2) or "horizontal" (1x4)
}) => {
  const { t } = useLanguage();
  const [states, setStates] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [tehsils, setTehsils] = useState([]);
  const [villages, setVillages] = useState([]);

  const [loadingStates, setLoadingStates] = useState(false);
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [loadingTehsils, setLoadingTehsils] = useState(false);
  const [loadingVillages, setLoadingVillages] = useState(false);

  // 1. Fetch All 36 States and Union Territories
  useEffect(() => {
    fetchStates();
  }, []);

  const fetchStates = async () => {
    setLoadingStates(true);
    try {
      const res = await api.get('/locations/states');
      setStates(res.data);
    } catch (err) {
      console.error('Failed to load states:', err);
    } finally {
      setLoadingStates(false);
    }
  };

  // 2. Fetch Districts when State changes
  useEffect(() => {
    if (!selectedState) {
      setDistricts([]);
      setTehsils([]);
      setVillages([]);
      return;
    }
    const stateObj = states.find(s => s.name === selectedState);
    if (stateObj) {
      fetchDistricts(stateObj.id);
    }
  }, [selectedState, states]);

  const fetchDistricts = async (stateId) => {
    setLoadingDistricts(true);
    try {
      const res = await api.get(`/locations/states/${stateId}/districts`);
      setDistricts(res.data);
    } catch (err) {
      console.error('Failed to load districts:', err);
      setDistricts([]);
    } finally {
      setLoadingDistricts(false);
    }
  };

  // 3. Fetch Tehsils when District changes
  useEffect(() => {
    if (!selectedDistrict) {
      setTehsils([]);
      setVillages([]);
      return;
    }
    const distObj = districts.find(d => d.name === selectedDistrict);
    if (distObj) {
      fetchTehsils(distObj.id);
    }
  }, [selectedDistrict, districts]);

  const fetchTehsils = async (distId) => {
    setLoadingTehsils(true);
    try {
      const res = await api.get(`/locations/districts/${distId}/tehsils`);
      setTehsils(res.data);
    } catch (err) {
      console.error('Failed to load tehsils:', err);
      setTehsils([]);
    } finally {
      setLoadingTehsils(false);
    }
  };

  // 4. Fetch Villages when Tehsil changes
  useEffect(() => {
    if (!selectedTehsil) {
      setVillages([]);
      return;
    }
    const tehObj = tehsils.find(t => t.name === selectedTehsil);
    if (tehObj) {
      fetchVillages(tehObj.id);
    }
  }, [selectedTehsil, tehsils]);

  const fetchVillages = async (tehsilId) => {
    setLoadingVillages(true);
    try {
      const res = await api.get(`/locations/tehsils/${tehsilId}/villages`);
      setVillages(res.data);
    } catch (err) {
      console.error('Failed to load villages:', err);
      setVillages([]);
    } finally {
      setLoadingVillages(false);
    }
  };

  const handleStateChange = (e) => {
    const newState = e.target.value;
    onChange({
      state: newState,
      district: '',
      tehsil: '',
      village: ''
    });
  };

  const handleDistrictChange = (e) => {
    const newDistrict = e.target.value;
    onChange({
      state: selectedState,
      district: newDistrict,
      tehsil: '',
      village: ''
    });
  };

  const handleTehsilChange = (e) => {
    const newTehsil = e.target.value;
    onChange({
      state: selectedState,
      district: selectedDistrict,
      tehsil: newTehsil,
      village: ''
    });
  };

  const handleVillageChange = (e) => {
    const newVillage = e.target.value;
    onChange({
      state: selectedState,
      district: selectedDistrict,
      tehsil: selectedTehsil,
      village: newVillage
    });
  };

  const containerClass = layout === "horizontal"
    ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3"
    : "grid grid-cols-1 sm:grid-cols-2 gap-4";

  return (
    <div className={containerClass}>
      {/* 1. State / UT Selection */}
      <div>
        <label className="block text-xs font-bold text-slate-700 mb-1">
          {t('upload.state', 'State / Union Territory')} {required && <span className="text-red-500">*</span>}
        </label>
        <div className="relative">
          <select
            value={selectedState || ''}
            onChange={handleStateChange}
            disabled={loadingStates}
            className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:ring-emerald-500 focus:border-emerald-500 disabled:bg-slate-100"
          >
            <option value="">Select State / UT ({states.length} available)</option>
            {states.map(s => (
              <option key={s.id} value={s.name}>
                {s.name} ({s.type === 'UNION_TERRITORY' ? 'UT' : 'State'})
              </option>
            ))}
          </select>
          {loadingStates && (
            <Loader2 className="w-3.5 h-3.5 animate-spin absolute right-3 top-3 text-emerald-700 pointer-events-none" />
          )}
        </div>
      </div>

      {/* 2. District Selection */}
      <div>
        <label className="block text-xs font-bold text-slate-700 mb-1">
          {t('upload.district', 'District')} {required && <span className="text-red-500">*</span>}
        </label>
        <div className="relative">
          <select
            value={selectedDistrict || ''}
            onChange={handleDistrictChange}
            disabled={!selectedState || loadingDistricts}
            className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:ring-emerald-500 focus:border-emerald-500 disabled:bg-slate-100"
          >
            <option value="">
              {!selectedState ? 'Select state first' : loadingDistricts ? 'Loading districts...' : districts.length === 0 ? 'No districts recorded' : 'Select District'}
            </option>
            {districts.map(d => (
              <option key={d.id} value={d.name}>{d.name}</option>
            ))}
          </select>
          {loadingDistricts && (
            <Loader2 className="w-3.5 h-3.5 animate-spin absolute right-3 top-3 text-emerald-700 pointer-events-none" />
          )}
        </div>
      </div>

      {/* 3. Tehsil / Taluk Selection */}
      <div>
        <label className="block text-xs font-bold text-slate-700 mb-1">
          {t('upload.tehsil', 'Tehsil / Taluk')} {required && <span className="text-red-500">*</span>}
        </label>
        <div className="relative">
          <select
            value={selectedTehsil || ''}
            onChange={handleTehsilChange}
            disabled={!selectedDistrict || loadingTehsils}
            className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:ring-emerald-500 focus:border-emerald-500 disabled:bg-slate-100"
          >
            <option value="">
              {!selectedDistrict ? 'Select district first' : loadingTehsils ? 'Loading tehsils...' : tehsils.length === 0 ? 'No tehsils recorded' : 'Select Tehsil / Taluk'}
            </option>
            {tehsils.map(t => (
              <option key={t.id} value={t.name}>{t.name}</option>
            ))}
          </select>
          {loadingTehsils && (
            <Loader2 className="w-3.5 h-3.5 animate-spin absolute right-3 top-3 text-emerald-700 pointer-events-none" />
          )}
        </div>
      </div>

      {/* 4. Village Selection */}
      <div>
        <label className="block text-xs font-bold text-slate-700 mb-1">
          {t('upload.village', 'Village / Mauza')} {required && <span className="text-red-500">*</span>}
        </label>
        <div className="relative">
          <select
            value={selectedVillage || ''}
            onChange={handleVillageChange}
            disabled={!selectedTehsil || loadingVillages}
            className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:ring-emerald-500 focus:border-emerald-500 disabled:bg-slate-100"
          >
            <option value="">
              {!selectedTehsil ? 'Select tehsil first' : loadingVillages ? 'Loading villages...' : villages.length === 0 ? 'No villages recorded' : 'Select Village / Mauza'}
            </option>
            {villages.map(v => (
              <option key={v.id} value={v.name}>{v.name}</option>
            ))}
          </select>
          {loadingVillages && (
            <Loader2 className="w-3.5 h-3.5 animate-spin absolute right-3 top-3 text-emerald-700 pointer-events-none" />
          )}
        </div>
      </div>
    </div>
  );
};
